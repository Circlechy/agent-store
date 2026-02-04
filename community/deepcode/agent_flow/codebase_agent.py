#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
import re
import os
import json
from typing import List, Dict
from pathlib import Path
from datetime import datetime

from openjiuwen.core.common.logging import logger
from examples.deepcode_agent.agents.react_agent import ChatAgent, AgentConfig
from examples.deepcode_agent.utils.code_indexing_utils import FileSummary, FileRelationship
from examples.deepcode_agent.prompts.user_prompts import get_relationship_prompt, get_analysis_prompt, get_filter_prompt

llm_config = {
    "model_provider": os.getenv("LLM_MODEL_PROVIDER", "openai"),
    "api_key": os.getenv("LLM_API_KEY", "sk-66e619e5e3ca4d86919f4f33238feeae"),
    "api_base": os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1"),
    "model_name": os.getenv("LLM_MODEL_NAME", "deepseek-chat"),
}


async def pre_filter_files(target_structure: str, file_tree: str, min_confidence_score: float) -> List[str]:
    filter_prompt = get_filter_prompt(target_structure=target_structure,
                                      file_tree=file_tree,
                                      min_confidence_score=min_confidence_score)
    filter_config = AgentConfig(
        name="filter_agent",
        llm_config=llm_config,
        system_prompt="You are a professional code analysis and project architecture expert, skilled at identifying code file functionality and relevance."
    )
    filter_agent = ChatAgent(filter_config)
    try:
        logger.info("Starting LLM pre-filtering of files...")
        llm_response = await filter_agent.ainvoke({"query": filter_prompt})

        # Parse JSON response
        match = re.search(r"\{.*}", llm_response.get("content", ""), re.DOTALL)
        if not match:
            logger.warning(
                "Unable to parse LLM filtering response, will use all files"
            )
            return []

        filter_data = json.loads(match.group(0))
        relevant_files = filter_data.get("relevant_files", [])

        # Extract file paths
        selected_files = []
        for file_info in relevant_files:
            file_path = file_info.get("file_path", "")
            confidence = file_info.get("confidence", 0.0)
            # Use configured minimum confidence threshold
            if file_path and confidence > min_confidence_score:
                selected_files.append(file_path)

        summary = filter_data.get("summary", {})
        logger.info(
            f"LLM filtering completed: {summary.get('relevant_files_count', len(selected_files))} relevant files selected"
        )
        logger.info(
            f"Filtering strategy: {summary.get('filtering_strategy', 'Not provided')}"
        )

        return selected_files

    except Exception as e:
        logger.error(f"LLM pre-filtering failed: {e}")
        logger.info("Will fallback to analyzing all files")
        return []

async def analyze_file_content(
        file_path: Path,
        max_file_size: int,
        code_base_path: Path,
        enable_content_caching: bool,
        content_cache: Dict[str, FileSummary],
        verbose_output: bool,
        max_content_length: int,
        max_cache_size: int
) -> FileSummary:
    try:
        # Check file size before reading
        file_size = file_path.stat().st_size
        if file_size > max_file_size:
            logger.warning(
                f"Skipping file {file_path} - size {file_size} bytes exceeds limit {max_file_size}"
            )
            return FileSummary(
                file_path=str(file_path.relative_to(code_base_path)),
                file_type="skipped - too large",
                main_functions=[],
                key_concepts=[],
                dependencies=[],
                summary=f"File skipped - size {file_size} bytes exceeds {max_file_size} byte limit",
                lines_of_code=0,
                last_modified=datetime.fromtimestamp(
                    file_path.stat().st_mtime
                ).isoformat(),
            )

        # Check cache if enabled
        cache_key = None
        if enable_content_caching:
            try:
                stats = file_path.stat()
                cache_key = f"{file_path}:{stats.st_mtime}:{stats.st_size}"
            except (OSError, PermissionError):
                cache_key = str(file_path)
            if cache_key in content_cache:
                if verbose_output:
                    logger.info(f"Using cached analysis for {file_path.name}")
                return content_cache[cache_key]

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Get file stats
        stats = file_path.stat()
        lines_of_code = len([line for line in content.split("\n") if line.strip()])

        # Truncate content based on config
        content_for_analysis = content[: max_content_length]
        content_suffix = "..." if len(content) > max_content_length else ""

        # Create analysis prompt
        analysis_prompt = get_analysis_prompt(
            file_path_name=file_path.name,
            content_for_analysis=content_for_analysis,
            content_suffix=content_suffix,
        )
        # Get LLM analysis with configured parameters
        analysis_config = AgentConfig(
            name="analysis_agent",
            llm_config=llm_config,
            system_prompt=""
            )
        analysis_agent = ChatAgent(analysis_config)

        try:
            llm_response = await analysis_agent.ainvoke({"query": analysis_prompt})
            # Try to parse JSON response
            match = re.search(r"\{.*}", llm_response.get("content", ""), re.DOTALL)
            analysis_data = json.loads(match.group(0))
        except json.JSONDecodeError:
            # Fallback to basic analysis if JSON parsing fails
            analysis_data = {
                "file_type": f"{file_path.suffix} file",
                "main_functions": [],
                "key_concepts": [],
                "dependencies": [],
                "summary": "File analysis failed - JSON parsing error",
            }

        file_summary = FileSummary(
            file_path=str(file_path.relative_to(code_base_path)),
            file_type=analysis_data.get("file_type", "unknown"),
            main_functions=analysis_data.get("main_functions", []),
            key_concepts=analysis_data.get("key_concepts", []),
            dependencies=analysis_data.get("dependencies", []),
            summary=analysis_data.get("summary", "No summary available"),
            lines_of_code=lines_of_code,
            last_modified=datetime.fromtimestamp(stats.st_mtime).isoformat(),
        )

        # Cache the result if caching is enabled
        if enable_content_caching and cache_key:
            content_cache[cache_key] = file_summary
            if len(content_cache) > max_cache_size:
                excess_count = len(content_cache) - max_cache_size + 10
                keys_to_remove = list(content_cache.keys())[:excess_count]

                for key in keys_to_remove:
                    del content_cache[key]

                if verbose_output:
                    logger.info(
                        f"Cache cleaned: removed {excess_count} entries, {len(content_cache)} entries remaining"
                    )

        return file_summary

    except Exception as e:
        logger.error(f"Error analyzing file {file_path}: {e}")
        return FileSummary(
            file_path=str(file_path.relative_to(code_base_path)),
            file_type="error",
            main_functions=[],
            key_concepts=[],
            dependencies=[],
            summary=f"Analysis failed: {str(e)}",
            lines_of_code=0,
            last_modified="",
        )

async def find_relationships(
        file_summary: FileSummary,
        min_confidence_score: float,
        target_structure: str,
        relationship_types: Dict[str, float],
        verbose_output: bool
) -> List[FileRelationship]:

    # Ensure target_structure is a string
    if target_structure is None:
        target_structure = ""
    
    # Build relationship type description from config
    relationship_type_desc = []
    for rel_type, weight in relationship_types.items():
        relationship_type_desc.append(f"- {rel_type} (priority: {weight})")

    relationship_prompt = get_relationship_prompt(
        file_summary=file_summary,
        target_structure=target_structure,
        relationship_type_desc=relationship_type_desc,
        min_confidence_score=min_confidence_score,
    )
    relationship_config = AgentConfig(
        name="relationship_agent",
        llm_config=llm_config,
        system_prompt=""
    )
    relationship_agent = ChatAgent(relationship_config)

    try:
        llm_response = await relationship_agent.ainvoke({"query": relationship_prompt})

        match = re.search(r"\{.*}", llm_response.get("content", ""), re.DOTALL)
        relationship_data = json.loads(match.group(0))

        relationships = []
        for rel_data in relationship_data.get("relationships", []):
            confidence_score = float(rel_data.get("confidence_score", 0.0))
            relationship_type = rel_data.get("relationship_type", "reference")

            # Validate relationship type is in config
            if relationship_type not in relationship_types:
                if verbose_output:
                    logger.warning(
                        f"Unknown relationship type '{relationship_type}', using 'reference'"
                    )
                relationship_type = "reference"

            # Apply configured minimum confidence filter
            if confidence_score > min_confidence_score:
                relationship = FileRelationship(
                    repo_file_path=file_summary.file_path,
                    target_file_path=rel_data.get("target_file_path", ""),
                    relationship_type=relationship_type,
                    confidence_score=confidence_score,
                    helpful_aspects=rel_data.get("helpful_aspects", []),
                    potential_contributions=rel_data.get(
                        "potential_contributions", []
                    ),
                    usage_suggestions=rel_data.get("usage_suggestions", ""),
                )
                relationships.append(relationship)

        return relationships

    except Exception as e:
        logger.error(
            f"Error finding relationships for {file_summary.file_path}: {e}"
        )
        return []