"""Merged Codebase Indexer that combines CodeIndexer and CodebaseIndexWorkflow functionality"""

import asyncio
import json
import os
import re
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from examples.deepcode_agent.agent_flow.codebase_agent import pre_filter_files, analyze_file_content, find_relationships
from examples.deepcode_agent.utils.code_indexing_utils import supported_extensions, skip_directories
from examples.deepcode_agent.utils.code_indexing_utils import FileSummary, FileRelationship, RepoIndex, \
    IndexerConfig

from openjiuwen.core.common.logging import logger


class MergedCodebaseIndexer:
    """Merged codebase indexer that combines CodeIndexer and CodebaseIndexWorkflow functionality"""

    def __init__(self,
                 code_base_path: Union[str, Path],
                 target_structure: Optional[str] = None,
                 output_dir: Optional[Union[str, Path]] = None,
                 enable_pre_filtering: bool = True,
                 indexer_config_path: Optional[str] = None):
        """Initialize the merged codebase indexer"""
        self.code_base_path = Path(code_base_path)
        self.output_dir = Path(output_dir) if output_dir else self.code_base_path / "code_indexes"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.target_structure = target_structure
        self.enable_pre_filtering = enable_pre_filtering
        self.indexer_config_path = indexer_config_path

        # Create configuration
        self.config = IndexerConfig(
            code_base_path=self.code_base_path,
            output_dir=self.output_dir
        )

        # Initialize attributes
        self.verbose_output = True
        self.include_metadata = True
        self.generate_statistics = True
        self.generate_summary = True
        self.index_filename_pattern = "{repo_name}_code_index.json"
        self.summary_filename = "codebase_summary.md"
        self.stats_filename = "codebase_statistics.json"
        self.initial_plan_path = None

        # Add configuration for LLM and relationships
        self.min_confidence_score = 0.3
        self.high_confidence_threshold = 0.7
        self.relationship_types = {
            "direct_match": 1.0,
            "partial_match": 0.8,
            "reference": 0.6,
            "utility": 0.4,
        }

        # Performance settings
        self.enable_concurrent_analysis = True
        self.max_concurrent_files = 5
        self.enable_content_caching = False
        self.max_cache_size = 100
        self.content_cache = {} if self.enable_content_caching else None
        self.request_delay = 0.1

        # File analysis settings
        self.supported_extensions = set(supported_extensions)
        self.skip_directories = set(skip_directories)
        self.max_file_size = 1048576  # 1MB
        self.max_content_length = 3000

        logger.info(f"Initialized MergedCodebaseIndexer with code base path: {self.code_base_path}")
        logger.info(f"Output directory: {self.output_dir}")

    def extract_file_tree_from_plan(self, plan_content: str) -> Dict[str, Any]:
        """Extract file tree structure from plan content"""
        # Pattern to match file tree blocks
        patterns = [
            r"```(?:json|markdown|)\s*(.*?)\s*```",
            r"```(?:json|markdown|)\s*([\s\S]*?)\s*```",
            r"```(?:json|markdown|)\s*([^`]*)\s*```",
        ]

        for pattern in patterns:
            match = re.search(pattern, plan_content, re.DOTALL)
            if match:
                tree_content = match.group(1)
                break
        else:
            tree_content = plan_content

        # Clean up the tree content
        tree_content = re.sub(r"^#.*?\n", "", tree_content, flags=re.MULTILINE)
        tree_content = re.sub(r"^\*\s*", "", tree_content, flags=re.MULTILINE)
        tree_content = re.sub(r"^-\s*", "", tree_content, flags=re.MULTILINE)
        tree_content = re.sub(r"^\s{2,}", "", tree_content, flags=re.MULTILINE)

        # Parse the JSON content
        try:
            file_tree = json.loads(tree_content)
            if isinstance(file_tree, dict):
                return file_tree
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON file tree, creating a minimal structure")

        # Fallback: create a minimal structure
        return {
            "name": "codebase",
            "type": "directory",
            "children": []
        }

    def load_target_structure_from_plan(self, plan_path: Union[str, Path]) -> Dict[str, Any]:
        """Load target structure from initial plan file"""
        plan_path = Path(plan_path)
        if not plan_path.exists():
            raise FileNotFoundError(f"Plan file not found: {plan_path}")

        with open(plan_path, "r", encoding="utf-8") as f:
            plan_content = f.read()

        return self.extract_file_tree_from_plan(plan_content)

    def load_or_create_indexer_config(self, initial_plan_path: Optional[Union[str, Path]] = None) -> IndexerConfig:
        """Load or create indexer configuration"""
        if initial_plan_path:
            self.initial_plan_path = Path(initial_plan_path)
            if self.initial_plan_path.exists():
                self.target_structure = self.load_target_structure_from_plan(self.initial_plan_path)

        # Create default configuration
        config = IndexerConfig(
            code_base_path=self.code_base_path,
            output_dir=self.output_dir,
            initial_plan_path=self.initial_plan_path,
            target_structure=self.target_structure
        )

        return config

    def generate_file_tree(self, repo_path: Path, max_depth: int = 5) -> str:
        """Generate file tree structure string for the repository"""
        tree_lines = []

        def add_to_tree(current_path: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return

            try:
                items = sorted(
                    current_path.iterdir(), key=lambda x: (x.is_file(), (x.name.lower() if x.name else ''))
                )
                # Filter out irrelevant directories and files
                items = [
                    item
                    for item in items
                    if not item.name.startswith(".")
                       and item.name not in self.skip_directories
                ]

                for i, item in enumerate(items):
                    is_last = i == len(items) - 1
                    current_prefix = "└── " if is_last else "├── "
                    tree_lines.append(f"{prefix}{current_prefix}{item.name}")

                    if item.is_dir():
                        extension_prefix = "    " if is_last else "│   "
                        add_to_tree(item, prefix + extension_prefix, depth + 1)
                    elif item.suffix.lower() in self.supported_extensions:
                        # Add file size information
                        try:
                            size = item.stat().st_size
                            if size > 1024:
                                size_str = f" ({size // 1024}KB)"
                            else:
                                size_str = f" ({size}B)"
                            tree_lines[-1] += size_str
                        except (OSError, PermissionError):
                            pass

            except PermissionError:
                tree_lines.append(f"{prefix}├── [Permission Denied]")
            except Exception as e:
                tree_lines.append(f"{prefix}├── [Error: {str(e)}]")

        tree_lines.append(f"{repo_path.name}/")
        add_to_tree(repo_path)
        return "\n".join(tree_lines)

    def get_all_repo_files(self, repo_path: Path) -> List[Path]:
        """Recursively get all supported files in a repository"""
        files = []
        try:
            for root, dirs, filenames in os.walk(repo_path):
                # Skip common non-code directories
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith(".") and d not in self.skip_directories
                ]

                for filename in filenames:
                    file_path = Path(root) / filename
                    if file_path.suffix.lower() in self.supported_extensions:
                        files.append(file_path)

        except Exception as e:
            logger.error(f"Error traversing {repo_path}: {e}")

        return files

    def filter_files_by_paths(self, all_files: List[Path], selected_paths: List[str], repo_path: Path) -> List[Path]:
        """Filter file list based on LLM-selected paths"""
        if not selected_paths:
            return all_files

        filtered_files = []

        for file_path in all_files:
            # Get path relative to repository root
            relative_path = str(file_path.relative_to(repo_path))

            # Check if it's in the selected list
            for selected_path in selected_paths:
                # Normalize path comparison
                if (
                        relative_path == selected_path
                        or relative_path.replace("\\", "/")
                        == selected_path.replace("\\", "/")
                        or selected_path in relative_path
                        or relative_path in selected_path
                ):
                    filtered_files.append(file_path)
                    break

        return filtered_files

    async def _analyze_single_file_with_relationships(self, file_path: Path, index: int, total: int) -> tuple:
        """Analyze a single file and its relationships (for concurrent processing)"""
        if self.verbose_output:
            logger.info(f"Analyzing file {index}/{total}: {file_path.name}")

        # Get file summary using the imported function
        file_summary = await analyze_file_content(file_path=file_path,
                                                  max_file_size=self.max_file_size,
                                                  code_base_path=self.code_base_path,
                                                  enable_content_caching=self.enable_content_caching,
                                                  content_cache=self.content_cache,
                                                  verbose_output=self.verbose_output,
                                                  max_content_length=self.max_content_length,
                                                  max_cache_size=self.max_cache_size)

        # Find relationships using the imported function
        relationships = await find_relationships(file_summary=file_summary,
                                                 target_structure=self.target_structure,
                                                 min_confidence_score=self.min_confidence_score,
                                                 relationship_types=self.relationship_types,
                                                 verbose_output=self.verbose_output)

        return file_summary, relationships

    async def _process_files_sequentially(self, files_to_analyze: list) -> tuple:
        """Process files sequentially (original method)"""
        file_summaries = []
        all_relationships = []

        for i, file_path in enumerate(files_to_analyze, 1):
            (
                file_summary,
                relationships,
            ) = await self._analyze_single_file_with_relationships(
                file_path, i, len(files_to_analyze)
            )
            file_summaries.append(file_summary)
            all_relationships.extend(relationships)

            # Add configured delay to avoid overwhelming the LLM API
            await asyncio.sleep(self.request_delay)

        return file_summaries, all_relationships

    async def _process_files_concurrently(self, files_to_analyze: List[Path]) -> Tuple[
        List[FileSummary], List[FileRelationship]]:
        """Process files concurrently with semaphore limiting"""
        file_summaries = []
        all_relationships = []

        # Create semaphore to limit concurrent tasks
        semaphore = asyncio.Semaphore(self.max_concurrent_files)
        tasks = []

        async def _process_with_semaphore(file_path: Path, index: int, total: int):
            async with semaphore:
                # Add a small delay to space out concurrent requests
                if index > 1:
                    await asyncio.sleep(
                        self.request_delay * 0.5
                    )  # Reduced delay for concurrent processing
                return await self._analyze_single_file_with_relationships(
                    file_path, index, total
                )

        try:
            # Create tasks for all files
            tasks = [
                _process_with_semaphore(file_path, i, len(files_to_analyze))
                for i, file_path in enumerate(files_to_analyze, 1)
            ]

            if self.verbose_output:
                logger.info(
                    f"Starting concurrent analysis of {len(tasks)} files..."
                )

            # Process tasks and collect results
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Failed to analyze file {files_to_analyze[i]}: {result}"
                    )
                    # Create error summary
                    error_summary = FileSummary(
                        file_path=str(
                            files_to_analyze[i].relative_to(self.code_base_path)
                        ),
                        file_type="error",
                        main_functions=[],
                        key_concepts=[],
                        dependencies=[],
                        summary=f"Concurrent analysis failed: {str(result)}",
                        lines_of_code=0,
                        last_modified=""
                    )
                    file_summaries.append(error_summary)
                else:
                    file_summary, relationships = result
                    file_summaries.append(file_summary)
                    all_relationships.extend(relationships)

        except Exception as e:
            logger.error(f"Concurrent processing failed: {e}")
            # Cancel any remaining tasks
            for task in tasks:
                if not task.done() and not task.cancelled():
                    task.cancel()

            # Wait for cancelled tasks to complete
            try:
                await asyncio.sleep(0.1)  # Brief wait for cancellation
            except Exception:
                pass

            # Fallback to sequential processing
            logger.info("Falling back to sequential processing...")
            return await self._process_files_sequentially(files_to_analyze)

        if self.verbose_output:
            logger.info(f"Concurrent analysis completed: {len(file_summaries)} files processed")

        return file_summaries, all_relationships

    async def process_repository(self, repo_dir: Path) -> RepoIndex:
        """Process a single repository and create complete index with optional concurrent processing"""
        repo_name = repo_dir.name
        logger.info(f"Processing repository: {repo_name}")

        # Step 1: Generate file tree
        logger.info("Generating file tree structure...")
        file_tree = self.generate_file_tree(repo_dir)

        # Step 2: Get all files
        all_files = self.get_all_repo_files(repo_dir)
        logger.info(f"Found {len(all_files)} files in {repo_name}")

        # Step 3: LLM pre-filtering of relevant files
        if self.enable_pre_filtering and self.target_structure:
            logger.info("Using LLM for file pre-filtering...")
            selected_file_paths = await pre_filter_files(
                self.target_structure, file_tree, self.min_confidence_score
            )
        else:
            logger.info("Pre-filtering is disabled or no target structure, will analyze all files")
            selected_file_paths = []

        # Step 4: Filter file list based on filtering results
        if selected_file_paths:
            files_to_analyze = self.filter_files_by_paths(
                all_files, selected_file_paths, repo_dir
            )
            logger.info(
                f"After LLM filtering, will analyze {len(files_to_analyze)} relevant files (from {len(all_files)} total)"
            )
        else:
            files_to_analyze = all_files
            logger.info("LLM filtering failed or disabled, will analyze all files")

        # Step 5: Analyze filtered files (concurrent or sequential)
        if self.enable_concurrent_analysis and len(files_to_analyze) > 1:
            logger.info(
                f"Using concurrent analysis with max {self.max_concurrent_files} parallel files"
            )
            file_summaries, all_relationships = await self._process_files_concurrently(
                files_to_analyze
            )
        else:
            logger.info("Using sequential file analysis")
            file_summaries, all_relationships = await self._process_files_sequentially(
                files_to_analyze
            )

        # Step 6: Create repository index
        repo_index = RepoIndex(
            repo_name=repo_name,
            total_files=len(all_files),  # Record original file count
            file_summaries=file_summaries,
            relationships=all_relationships,
            analysis_metadata={
                "analysis_date": datetime.now().isoformat(),
                "target_structure_analyzed": self.target_structure[:200] + "..." if self.target_structure else "None",
                "total_relationships_found": len(all_relationships),
                "high_confidence_relationships": len(
                    [
                        r
                        for r in all_relationships
                        if r.confidence_score > self.high_confidence_threshold
                    ]
                ),
                "analyzer_version": "1.4.0",  # Updated version to reflect augmented LLM support
                "pre_filtering_enabled": self.enable_pre_filtering,
                "files_before_filtering": len(all_files),
                "files_after_filtering": len(files_to_analyze),
                "filtering_efficiency": round(
                    (1 - len(files_to_analyze) / len(all_files)) * 100, 2
                )
                if all_files
                else 0,
                "config_file_used": self.indexer_config_path,
                "min_confidence_score": self.min_confidence_score,
                "high_confidence_threshold": self.high_confidence_threshold,
                "concurrent_analysis_used": self.enable_concurrent_analysis,
                "content_caching_enabled": self.enable_content_caching,
                "cache_hits": len(self.content_cache) if self.content_cache else 0,
            },
        )

        return repo_index

    def export_index(self, repo_index: RepoIndex, index_file: Path) -> None:
        """Export repository index to JSON file with proper serialization"""

        # Custom JSON encoder to handle complex types
        class EnhancedJSONEncoder(json.JSONEncoder):
            def default(self, o):
                if hasattr(o, '__dict__'):
                    return o.__dict__
                return json.JSONEncoder.default(self, o)

        # Convert dataclasses to dictionaries with custom encoder
        index_dict = asdict(repo_index)

        # Create parent directory if it doesn't exist
        index_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to JSON file
        with open(index_file, "w", encoding="utf-8") as f:
            if self.include_metadata:
                json.dump(index_dict, f, indent=2, ensure_ascii=False, cls=EnhancedJSONEncoder)
            else:
                index_data = index_dict
                index_data.pop("analysis_metadata", None)
                json.dump(index_data, f, indent=2, ensure_ascii=False, cls=EnhancedJSONEncoder)

        logger.info(f"Exported index to {index_file}")
        logger.info(
            f"Index contains {len(repo_index.file_summaries)} file summaries and {len(repo_index.relationships)} relationships")

    def generate_summary_markdown(self, repo_index: RepoIndex) -> str:
        """Generate comprehensive markdown summary of the codebase"""
        # Create initial summary with overall statistics
        markdown = f"""# Codebase Intelligence Report: {repo_index.repo_name}

## Executive Summary
Repository: {repo_index.repo_name}
Total Files: {repo_index.total_files}
Analyzed Files: {len(repo_index.file_summaries)}
Relationships Identified: {len(repo_index.relationships)}

## Analysis Methodology
"""

        # Add methodology section from metadata
        metadata = repo_index.analysis_metadata
        markdown += f"""- **Pre-filtering Enabled:** {metadata.get('pre_filtering_enabled', False)}
- **Filtering Efficiency:** {metadata.get('filtering_efficiency', 0)}%
- **Min Confidence Score:** {metadata.get('min_confidence_score', 0.3)}
- **Analysis Date:** {metadata.get('analysis_date', 'N/A')}
- **Analyzer Version:** {metadata.get('analyzer_version', 'N/A')}

## File Summaries
"""

        # Add file summaries sorted by importance
        for file_summary in sorted(repo_index.file_summaries,
                                   key=lambda x: x.file_path):
            markdown += f"""### {file_summary.file_path}

- **Type:** {file_summary.file_type}
- **Lines:** {file_summary.lines_of_code}
- **Modified:** {getattr(file_summary, 'last_modified', 'N/A')}

**Key Concepts:** {', '.join(file_summary.key_concepts[:5])}...

**Main Functions:** {', '.join(file_summary.main_functions[:3])}...

**Summary:** {file_summary.summary[:150]}...

"""

        # Add relationships section if relationships exist
        if repo_index.relationships:
            markdown += """
## Relationship Analysis

### High Confidence Matches (>70%)
"""

            # Group relationships by confidence score
            high_conf_rels = [r for r in repo_index.relationships
                              if r.confidence_score >= metadata.get('high_confidence_threshold', 0.7)]
            other_rels = [r for r in repo_index.relationships
                          if r.confidence_score < metadata.get('high_confidence_threshold', 0.7)]

            # Add high confidence relationships
            for relationship in high_conf_rels[:5]:  # Limit to top 5
                markdown += f"""#### {relationship.repo_file_path} → {relationship.target_file_path}

- **Type:** {relationship.relationship_type}
- **Confidence:** {relationship.confidence_score:.2f}
- **Helpful Aspects:** {', '.join(relationship.helpful_aspects[:3])}
- **Contributions:** {relationship.potential_contributions[0][:100]}...

"""

            if len(high_conf_rels) > 5:
                markdown += f"\n*And {len(high_conf_rels) - 5} more high-confidence relationships...*\n\n"

            # Add other relationships count
            if other_rels:
                markdown += f"\n### Other Relationships ({len(other_rels)})\n"

        # Add technical metadata section
        markdown += """
## Technical Metadata
"""

        for key, value in metadata.items():
            if key not in ['analysis_date', 'analyzer_version', 'pre_filtering_enabled',
                           'filtering_efficiency', 'min_confidence_score', 'high_confidence_threshold']:
                markdown += f"- **{key}:** {value}\n"

        return markdown

    async def build_all_indexes(self) -> Dict[str, str]:
        """Build indexes for all repositories in code_base"""
        if not self.code_base_path.exists():
            raise FileNotFoundError(f"Code base path does not exist: {self.code_base_path}")

        # Get all repository directories
        repo_dirs = [
            d for d in self.code_base_path.iterdir() if d.is_dir() and not d.name.startswith(".")
        ]

        if not repo_dirs:
            raise ValueError(f"No repositories found in {self.code_base_path}")

        logger.info(f"Found {len(repo_dirs)} repositories to process")

        # Process each repository
        output_files = {}
        statistics_data = []

        for repo_dir in repo_dirs:
            try:
                # Process repository
                repo_index = await self.process_repository(repo_dir)

                # Generate output filename
                output_filename = self.index_filename_pattern.format(repo_name=repo_index.repo_name)
                output_file = self.output_dir / output_filename

                # Export index using the new method
                self.export_index(repo_index, output_file)

                output_files[repo_index.repo_name] = str(output_file)

                # Collect statistics
                if self.generate_statistics:
                    stats = self._extract_repository_statistics(repo_index)
                    statistics_data.append(stats)

            except Exception as e:
                logger.error(f"Failed to process repository {repo_dir.name}: {e}")
                continue

        # Generate reports
        if self.generate_summary and output_files:
            summary_path = self.generate_summary_report(output_files)
            logger.info(f"Generated summary report: {summary_path}")

        if self.generate_statistics and statistics_data:
            stats_path = self.generate_statistics_report(statistics_data)
            logger.info(f"Generated statistics report: {stats_path}")

        return output_files

    def _extract_repository_statistics(self, repo_index: RepoIndex) -> Dict[str, Any]:
        """Extract statistical information from a repository index"""
        metadata = repo_index.analysis_metadata

        # Count relationship types
        relationship_type_counts = {}
        for rel in repo_index.relationships:
            rel_type = rel.relationship_type
            relationship_type_counts[rel_type] = relationship_type_counts.get(rel_type, 0) + 1

        # Count file types
        file_type_counts = {}
        for file_summary in repo_index.file_summaries:
            file_type = file_summary.file_type
            file_type_counts[file_type] = file_type_counts.get(file_type, 0) + 1

        # Calculate statistics
        total_lines = sum(fs.lines_of_code for fs in repo_index.file_summaries)
        avg_lines = total_lines / len(repo_index.file_summaries) if repo_index.file_summaries else 0
        avg_confidence = sum(r.confidence_score for r in repo_index.relationships) / len(
            repo_index.relationships) if repo_index.relationships else 0

        return {
            "repo_name": repo_index.repo_name,
            "total_files": repo_index.total_files,
            "analyzed_files": len(repo_index.file_summaries),
            "total_relationships": len(repo_index.relationships),
            "high_confidence_relationships": metadata.get("high_confidence_relationships", 0),
            "relationship_type_counts": relationship_type_counts,
            "file_type_counts": file_type_counts,
            "total_lines_of_code": total_lines,
            "average_lines_per_file": round(avg_lines, 2),
            "average_confidence_score": round(avg_confidence, 3),
            "filtering_efficiency": metadata.get("filtering_efficiency", 0),
            "concurrent_analysis_used": metadata.get("concurrent_analysis_used", False),
            "cache_hits": metadata.get("cache_hits", 0),
            "analysis_date": metadata.get("analysis_date", "unknown"),
        }

    def generate_statistics_report(self, statistics_data: List[Dict[str, Any]]) -> str:
        """Generate a detailed statistics report"""
        stats_path = self.output_dir / self.stats_filename

        # Calculate aggregate statistics
        total_repos = len(statistics_data)
        total_files_analyzed = sum(stat["analyzed_files"] for stat in statistics_data)

        # Write statistics to JSON file
        statistics_report = {
            "total_repositories": total_repos,
            "total_files_analyzed": total_files_analyzed,
            "repository_statistics": statistics_data,
            "generated_at": datetime.now().isoformat()
        }

        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(statistics_report, f, indent=2, ensure_ascii=False)

        return str(stats_path)

    def generate_summary_report(self, output_files: Dict[str, str]) -> str:
        """Generate a summary report of all indexed repositories"""
        summary_path = self.output_dir / self.summary_filename

        # Create summary content
        summary_content = "# Codebase Index Summary\n\n"
        summary_content += f"Generated on: {datetime.now().isoformat()}\n\n"
        summary_content += f"Total repositories indexed: {len(output_files)}\n\n"

        # Add repository details
        for repo_name, file_path in output_files.items():
            summary_content += f"## {repo_name}\n"
            summary_content += f"Index file: {file_path}\n\n"

        # Write summary to markdown file
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary_content)

        return str(summary_path)

    async def run_indexing_workflow(self, initial_plan_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Run the complete indexing workflow"""
        logger.info("Starting codebase indexing workflow...")
        start_time = time.time()

        try:
            # Load configuration
            config = self.load_or_create_indexer_config(initial_plan_path)

            # Apply configuration
            self.code_base_path = config.code_base_path
            self.output_dir = config.output_dir
            self.target_structure = config.target_structure

            # Check codebase path
            if not self.code_base_path.exists():
                raise FileNotFoundError(f"Codebase directory not found: {self.code_base_path}")

            logger.info(f"Using codebase path: {self.code_base_path}")
            logger.info(f"Using output directory: {self.output_dir}")

            # Build indexes
            output_files = await self.build_all_indexes()

            # Calculate execution time
            execution_time = time.time() - start_time

            # Prepare results
            results = {
                "success": True,
                "message": "Codebase indexing completed successfully",
                "execution_time": round(execution_time, 2),
                "output_files": output_files,
                "statistics": {
                    "total_repositories": len(output_files),
                    "generated_at": datetime.now().isoformat()
                }
            }

            logger.info(f"Indexing workflow completed in {execution_time:.2f} seconds")
            logger.info(f"Indexed {len(output_files)} repositories")

            return results

        except Exception as e:
            logger.error(f"Indexing workflow failed: {e}")
            return {
                "success": False,
                "message": str(e),
                "execution_time": round(time.time() - start_time, 2)
            }

    @staticmethod
    async def run_codebase_indexing(code_base_path: Union[str, Path], output_dir: Optional[Union[str, Path]] = None,
                                    initial_plan_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Convenience method to run codebase indexing"""
        indexer = MergedCodebaseIndexer(code_base_path, output_dir)
        return await indexer.run_indexing_workflow(initial_plan_path)


async def orchestrate_codebase_intelligence_agent(dir_info: Dict[str, Any]) -> Dict[str, Any]:
    """Orchestrate the codebase intelligence agent"""
    
    # Extract paper_dir from dir_info and construct code_base_dir
    paper_dir = dir_info.get("paper_dir")
    if not paper_dir:
        raise ValueError("paper_dir not found in dir_info")
    
    code_base_dir = os.path.join(paper_dir, "code_base")
    code_base_path = Path(code_base_dir)

    # Check if codebase directory exists, if not create it
    if not code_base_path.exists():
        os.makedirs(code_base_path, exist_ok=True)
        logger.info(f"Created codebase directory: {code_base_path}")
        return {"status": "empty", "message": "No GitHub repositories found in codebase directory"}

    if not code_base_path.is_dir():
        raise NotADirectoryError(f"Codebase path is not a directory: {code_base_path}")
    
    # Get all GitHub repositories in code_base_dir
    repo_dirs = []
    for item in code_base_path.iterdir():
        if item.is_dir():
            repo_dirs.append(item)
    
    if not repo_dirs:
        logger.info(f"No GitHub repositories found in: {code_base_path}")
        return {"status": "empty", "message": "No GitHub repositories found in codebase directory"}
    
    # Process each repository
    all_results = {}
    for repo_dir in repo_dirs:
        repo_name = repo_dir.name
        logger.info(f"Processing GitHub repository: {repo_name}")
        
        try:
            # Run indexing workflow for the repository
            indexer = MergedCodebaseIndexer(repo_dir)
            results = await indexer.run_indexing_workflow(dir_info.get("initial_plan_path"))
            all_results[repo_name] = results
        except Exception as e:
            logger.error(f"Error processing repository {repo_name}: {str(e)}")
            all_results[repo_name] = {"status": "error", "message": str(e)}
    
    return {"status": "completed", "repositories": all_results}