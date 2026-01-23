#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
import asyncio
import json
import os
import yaml
from typing import Tuple, Dict, Any, List, Optional
from mcp import StdioServerParameters
from dotenv import load_dotenv

from openjiuwen.core.common.logging import logger
from examples.deepcode_agent.agents import ReActAgent, AgentConfig
from openjiuwen.core.utils.tool.mcp.base import ToolServerConfig
from examples.deepcode_agent.prompts.sys_prompts import PAPER_INPUT_ANALYZER_PROMPT, PAPER_DOWNLOADER_PROMPT, DOCUMENT_SEGMENTATION_PROMPT
from examples.deepcode_agent.prompts.user_prompts import (RESOURCE_PROCESSOR_USER_PROMPT, ANALYZE_AND_PREPARE_DOCUMENT_USER_PROMPT,
                                                          GET_DOCUMENT_OVERVIEW_USER_PROMPT, VALIDATE_SEGMENTATION_QUALITY_USER_PROMPT,
                                                          CONCEPT_ANALYSIS_PROMPT, ALGORITHM_ANALYSIS_PROMPT, CODE_PLANNING_PROMPT,
                                                          PAPER_REFERENCE_ANALYZER_PROMPT, GITHUB_DOWNLOADER_PROMPT)
from examples.deepcode_agent.utils.utils import extract_clean_json
from examples.deepcode_agent.tools.pdf_downloader import move_file_to, download_file_to
from examples.deepcode_agent.utils.file_processor import FileProcessor
from examples.deepcode_agent.utils.llm_utils import get_token_limits
from examples.deepcode_agent.agent_flow.agent_aggregation import AgentAggregation
from examples.deepcode_agent.agent_flow.code_implementation_flow_iterative import IterativeCodeFlow

# 加载.env文件
load_dotenv()

class MultiAgentResearchFlow:
    # Todo 功能待与 deepcode execute_multi_agent_research_pipeline对齐

    def __init__(self):
        # Todo 和 deepcode 配置参数对齐
        self.enable_index = True
        self.llm_config = {
            "model_provider": os.getenv("LLM_MODEL_PROVIDER"),
            "api_key": os.getenv("LLM_API_KEY"),
            "api_base": os.getenv("LLM_API_BASE"),
            "model_name": os.getenv("LLM_MODEL_NAME"),
            }

    async def initialize_agents(self):
        # Todo 所有Agent初始化
        # 每个Agent初始化使用一个方法
        await self._initialize_research_analyzer_agent()
        await self._initialize_resource_processor_agent()
        await self._initialize_document_segmentation_agent()
        await self._initialize_code_planning_agent()
        await self._initialize_citation_discovery_agent()
        await self._initialize_github_acquisition_agent()

    async def _initialize_research_analyzer_agent(self):
        # 初始化研究分析代理
        self.analyzer_agent = ReActAgent(
            AgentConfig(
                name="ResearchAnalyzerAgent",
                llm_config=self.llm_config,
                system_prompt=PAPER_INPUT_ANALYZER_PROMPT,
            )
        )

    async def _initialize_resource_processor_agent(self):
        # 初始化资源处理器代理
        self.processor_agent = ReActAgent(
            AgentConfig(
                name="ResourceProcessorAgent",
                llm_config=self.llm_config,
                system_prompt=PAPER_DOWNLOADER_PROMPT,
            )
        )
        
        # 为资源处理器代理准备MCP工具服务器配置
        pdf_downloader_path = os.getenv("PDF_DOWNLOADER_PATH")

        mcp_config = ToolServerConfig(
            server_name="file-downloader",
            params=StdioServerParameters(
                command="python", 
                args=[pdf_downloader_path]
            ),
            client_type="stdio"
        )
        
        await self.processor_agent.add_mcps([mcp_config])

    async def _initialize_document_segmentation_agent(self):
        # 初始化文档分割代理
        self.document_segmentation_agent = ReActAgent(
            AgentConfig(
                name="DocumentSegmentationCoordinator",
                llm_config=self.llm_config,
                system_prompt=DOCUMENT_SEGMENTATION_PROMPT,
            )
        )

        document_segmentation_server_path = os.getenv("DOCUMENT_SEGMENTATION_PATH")

        mcp_config = ToolServerConfig(
            server_name="document-segmentation-server",
            params=StdioServerParameters(
                command="python",
                args=[document_segmentation_server_path]
            ),
            client_type="stdio"
        )

        await self.document_segmentation_agent.add_mcps([mcp_config])
        
    async def _initialize_code_planning_agent(self):
        # 初始化代码规划及聚合器
        server_names = self._get_server_names()
        self.architecture_agent = ReActAgent(
            AgentConfig(
                name="ArchitectureSpecialist",
                llm_config=self.llm_config,
                system_prompt=CONCEPT_ANALYSIS_PROMPT,
                server_names=server_names
            )
        )
        
        self.algorithm_agent = ReActAgent(
            AgentConfig(
                name="AlgorithmSpecialist",
                llm_config=self.llm_config,
                system_prompt=ALGORITHM_ANALYSIS_PROMPT,
                server_names=server_names
            )
        )
        
        self.lead_planner_agent = ReActAgent(
            AgentConfig(
                name="LeadArchitect",
                llm_config=self.llm_config,
                system_prompt=CODE_PLANNING_PROMPT,
                server_names=server_names
            )
        )

        self.planning_engine = AgentAggregation(
            aggregator=self.lead_planner_agent,
            source_agents=[self.architecture_agent, self.algorithm_agent]
        )

    async def _initialize_citation_discovery_agent(self):
        # 初始化引用发现代理
        server_names = self._get_server_names()
        
        self.citation_miner = ReActAgent(
            AgentConfig(
                name="CitationDiscoverySpecialist",
                llm_config=self.llm_config,
                system_prompt=PAPER_REFERENCE_ANALYZER_PROMPT,
                server_names=server_names
            )
        )

    async def _initialize_github_acquisition_agent(self):
        """
        [Phase 6 Init] 初始化 GitHub 仓库获取专用代理
        """
        # 1. 初始化 Agent
        # 我们需要在 server_names 中显式包含 "filesystem"
        # 这样 Agent 就能从 mcp_agent.config.yaml 中加载文件系统工具
        self.repo_acquisitor = ReActAgent(
            AgentConfig(
                name="RepoAcquisitionSpecialist",
                llm_config=self.llm_config,
                system_prompt=GITHUB_DOWNLOADER_PROMPT,
                server_names=["filesystem"]  # <--- [New] 显式挂载文件系统
            )
        )

        # 2. 动态加载 GitHub Downloader MCP
        # ... (保持之前的动态加载逻辑不变) ...
        git_tool_path = os.getenv("GITHUB_DOWNLOADER_PATH", "tools/git_command.py")
        
        if os.path.exists(git_tool_path):
            # ... (mcp_config 配置逻辑不变) ...
            mcp_config = ToolServerConfig(
                server_name="github-downloader", 
                params=StdioServerParameters(
                    command="python",
                    args=[git_tool_path],
                    env={"PYTHONPATH": "."}
                ),
                client_type="stdio"
            )
            # add_mcps 会将这个新工具追加到已有的 filesystem 工具后面
            await self.repo_acquisitor.add_mcps([mcp_config])
        else:
            logger.error(f"❌ GitHub tool not found at {git_tool_path}")

    async def ainvoke(self, input_source: str):
        # Todo 对应 execute_multi_agent_research_pipeline 方法，入参需对齐
        # Phase 0: Workspace Setup
        workspace_dir = self._prepare_workspace()

        # Phase 1: Input Processing and validation
        self._input_processing_and_validation(input_source)

        # Phase 2: Research Analysis and Resource Processing
        analysis_result, resource_processing_result = await self._analysis_processing_input(input_source)

        # Phase 3: WorkSpace Infrastructure Synthesis
        dir_info = await self._process_workspace_infrastructure(
            resource_processing_result, workspace_dir
        )
        # await asyncio.sleep(5)

        # Phase 3.5: Document Segmentation and Preprocessing
        doc_split_result = await self._document_preprocessing_agent(dir_info)

        # 根据预处理结果状态处理日志输出
        process_status = doc_split_result.get("status", "")
        if process_status == "success":
            logger.info("✅ 文档预处理流程执行完成！")
            logger.info(f"   📊 分割功能启用状态: {dir_info.get('use_segmentation', False)}")
            if dir_info.get("segments_ready", False):
                split_dir = doc_split_result.get("segments_dir", "未指定")
                logger.info(f"   📁 分割文件存储目录: {split_dir}")

        elif process_status == "fallback_to_traditional":
            err_detail = doc_split_result.get("original_error", "未知错误")
            logger.warning("⚠️ 文档智能分割失败，切换至传统处理模式")
            logger.warning(f"   错误详情: {err_detail}")

        else:
            err_msg = doc_split_result.get("error_message", "未知问题")
            logger.error(f"⚠️ 文档预处理过程出现异常: {err_msg}")

        # Phase 4: Code Planning Orchestration
        await self._orchestrate_code_planning(dir_info)

        # Phase 5: Reference Intelligence
        # reference_result = await self._execute_reference_mining_workflow(dir_info)

        # Phase 6: Repository Acquisition Automation
        # await self._execute_repo_acquisition_workflow(
        #     reference_data=reference_result,
        #     dir_map=dir_info,  # 传入路径字典
        # )
        #
        # # Phase 7: Codebase Intelligence Orchestration
        # await orchestrate_codebase_intelligence_agent(dir_info)


        # Phase 8: Code Implementation Synthesis
        logger.info("\n" + "="*60)
        logger.info("[Phase 8] Starting Code Implementation Synthesis")
        logger.info("="*60)
        
        try:
            
            # 初始化代码实现控制器
            code_impl_controller = IterativeCodeFlow()
            await code_impl_controller.initialize()
            
            # 执行代码实现
            impl_result = await code_impl_controller.execute(
                plan_file_path=dir_info["initial_plan_path"],
                target_directory=dir_info["paper_dir"],
                enable_read_tools=True
            )
            
            # 记录实现结果
            if impl_result["status"] in ("success", "partial"):
                logger.info(f"✅ Code Implementation completed with status: {impl_result['status']}")
                metrics = impl_result.get("metrics", {})
                logger.info(f"📊 Implemented {metrics.get('succeeded', 0)}/{metrics.get('total_files', 0)} files")
                logger.info(f"⏱️  Duration: {metrics.get('duration_seconds', 0)}s")
            else:
                logger.error(f"❌ Code Implementation failed: {impl_result.get('message')}")
                
        except Exception as e:
            logger.error(f"❌ Failed to execute Code Implementation: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Phase 9: Final Status Report
        logger.info("\n" + "="*60)
        logger.info("[Phase 9] Final Status Report")
        logger.info("="*60)
        logger.info("Multi-agent research and implementation pipeline completed!")

    def _prepare_workspace(self) -> str:
        workspace_dir = os.path.join(os.getcwd(), "deepcode_lab")
        os.makedirs(workspace_dir, exist_ok=True)

        logger.info(f"Deepcode Agent workspace directory: {workspace_dir}")
        if self.enable_index:
            logger.info("Deepcode Agent index enabled")
        else:
            logger.info("Deepcode Agent index disabled")
        return workspace_dir

    def _input_processing_and_validation(self, input_source: str) -> str:
        """解析输入源，处理file://协议的路径转换"""
        if input_source.startswith("file://"):
            file_path = input_source[len("file://"):]
            # Windows系统移除路径开头的/
            if os.name == "nt":
                file_path = file_path.lstrip("/") if file_path.startswith("/") else file_path
            return file_path
        return input_source

    async def _analysis_processing_input(self, input_source: str) -> Tuple[str, str]:
        # 定义支持的文件扩展名和前缀
        supported_extensions = (".pdf", ".docx", ".txt", ".html", ".md")
        supported_prefixes = ("http", "file://")

        # 检查输入源是否为字符串且符合处理条件
        if isinstance(input_source, str):
            is_supported_ext = input_source.endswith(supported_extensions)
            is_supported_prefix = input_source.startswith(supported_prefixes)
            if is_supported_ext or is_supported_prefix:
                # 执行研究分析代理
                analysis_result = await self._run_research_analyzer(input_source)

                await asyncio.sleep(5)

                # 下载结果处理
                download_result = await self._run_resource_processor(analysis_result)
                return analysis_result, download_result

        # 不符合条件时，下载结果为输入源本身，分析结果为None
        return None, input_source

    async def _run_research_analyzer(self, prompt_text: str) -> str:
        """执行研究分析逻辑"""
        # 输入校验
        if not prompt_text or prompt_text.strip() == "":
            raise ValueError("Empty or None prompt_text provided to run_research_analyzer")

        try:
            # 使用已初始化的分析代理获取结果
            result = await self.analyzer_agent.ainvoke({"query": prompt_text})
            
            # 提取结果内容
            raw_result = result.get("content", "")
            
            # 校验LLM结果
            if not raw_result:
                raise ValueError("LLM returned empty result")

            # 提取并清洗JSON结果
            try:
                clean_result = extract_clean_json(raw_result)
            except Exception as e:
                if logger:
                    logger.error(f"JSON extraction failed: {str(e)}, raw result: {raw_result}")
                raise

            # 校验清洗后的结果
            if not clean_result or clean_result.strip() == "":
                raise ValueError("JSON extraction resulted in empty output")

            # 记录日志
            if logger and hasattr(logger, "log_response"):
                logger.log_response(
                    clean_result,
                    model="ResearchAnalyzer",
                    agent="ResearchAnalyzerAgent",
                )

            return clean_result

        except Exception as e:
            if logger:
                logger.error(f"Research analyzer failed: {str(e)}")
            raise

    async def _run_resource_processor(self, analysis_result: str) -> str:
        """
        处理资源下载与文件存储，生成论文目录并处理不同类型的输入源

        Args:
            analysis_result: 分析结果的JSON字符串
            logger: 日志记录实例

        Returns:
            str: 处理结果的JSON字符串
        """
        # 初始化论文目录
        papers_dir = "./deepcode_lab/papers"
        os.makedirs(papers_dir, exist_ok=True)

        # 生成论文ID
        next_id = self._get_next_paper_id(papers_dir)
        paper_dir = os.path.join(papers_dir, str(next_id))
        os.makedirs(paper_dir, exist_ok=True)

        logger.info(f"📋 Paper ID: {next_id}")
        logger.info(f"📂 Paper directory: {paper_dir}")

        try:
            # 解析分析结果
            analysis_data = json.loads(analysis_result)
            source_path = analysis_data.get("path") or analysis_data.get("input_path")
            input_type = analysis_data.get("input_type", "unknown")

            logger.info(f"📥 Processing {input_type}: {source_path}")

            # 尝试直接处理文件/URL
            direct_result = await self._process_direct_source(
                input_type, source_path, paper_dir, next_id
            )

            if direct_result["success"]:
                # 直接处理成功，构造结果
                result = json.dumps({
                    "status": "success",
                    "paper_id": next_id,
                    "paper_dir": paper_dir,
                    "file_path": os.path.join(paper_dir, f"{next_id}.md"),
                    "message": f"File successfully processed to {paper_dir}",
                    "operation_details": direct_result["details"]
                })
            else:
                # 直接处理失败，调用代理处理
                logger.info(f"🤖 Falling back to LLM agent for: {input_type} - {source_path}")

                # 构造上下文信息（包含之前的操作结果）
                context = f"\nPrevious attempt result: {direct_result['details']}"

                # 格式化用户提示信息
                message = RESOURCE_PROCESSOR_USER_PROMPT.format(
                    paper_dir=paper_dir,
                    source_path=source_path,
                    input_type=input_type,
                    next_id=next_id,
                    next_id_2=next_id,
                    context=context,
                )

                # 使用已初始化的资源处理器代理获取结果
                agent_result = await self.processor_agent.ainvoke({"query": message})
                result = agent_result.get("content", "")

            return result

        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.error(f"❌ Error processing resource: {e}")
            # 异常处理，返回部分成功结果
            return json.dumps({
                "status": "partial",
                "paper_id": next_id,
                "paper_dir": paper_dir,
                "message": f"Paper directory created at {paper_dir}, manual file placement may be needed"
            })

    def _get_next_paper_id(self, papers_dir: str) -> int:
        """计算下一个论文ID（遍历现有目录并取最大值+1）"""
        try:
            existing_ids = []
            for d in os.listdir(papers_dir):
                dir_path = os.path.join(papers_dir, d)
                if os.path.isdir(dir_path) and d.isdigit():
                    existing_ids.append(int(d))
            return max(existing_ids) + 1 if existing_ids else 1
        except Exception:
            return 1

    async def _process_direct_source(
            self, input_type: str, source_path: str, paper_dir: str, paper_id: int
    ) -> dict:
        """直接处理文件或URL，返回处理结果字典"""
        operation_result = None
        success = False

        if input_type == "file" and source_path and os.path.exists(source_path):
            logger.info(f"📄 Direct file copy: {source_path} -> {paper_dir}")
            try:
                operation_result = await move_file_to(
                    source=source_path,
                    destination=paper_dir,
                    filename=f"{paper_id}.pdf"
                )
                success = "[SUCCESS]" in operation_result and "[ERROR]" not in operation_result
                if success:
                    logger.info(f"✅ Direct file copy succeeded:\n{operation_result}")
                else:
                    logger.warning(f"⚠️ Direct file copy had issues: {operation_result}")
            except Exception as e:
                logger.warning(f"⚠️ Direct file copy failed: {e}")

        elif input_type == "url" and source_path:
            logger.info(f"🌐 Direct URL download: {source_path} -> {paper_dir}")
            try:
                operation_result = await download_file_to(
                    url=source_path,
                    destination=paper_dir,
                    filename=f"{paper_id}.pdf"
                )
                success = "[SUCCESS]" in operation_result and "[ERROR]" not in operation_result
                if success:
                    logger.info(f"✅ Direct download succeeded:\n{operation_result}")
                else:
                    logger.warning(f"⚠️ Direct download had issues: {operation_result}")
            except Exception as e:
                logger.warning(f"⚠️ Direct download failed: {e}")

        return {
            "success": success,
            "details": operation_result
        }

    async def _process_workspace_infrastructure(self, download_result: str, workspace_dir: str):
        file_process_result = await FileProcessor.process_file_input(
            download_result,
            base_dir=workspace_dir
        )
        paper_dir = file_process_result["paper_dir"]

        # 记录工作空间合成日志
        logger.info(
            f"Intelligent workspace infrastructure synthesized: "
            f"Base workspace: {workspace_dir or 'auto-detected'}, "
            f"Research workspace: {paper_dir}, "
            f"AI-driven path optimization: active"
        )

        # 构造返回结果字典
        return {
            "paper_dir": paper_dir,
            "standardized_text": file_process_result["standardized_text"],
            "reference_path": os.path.join(paper_dir, "reference.txt"),
            "initial_plan_path": os.path.join(paper_dir, "initial_plan.txt"),
            "download_path": os.path.join(paper_dir, "github_download.txt"),
            "index_report_path": os.path.join(paper_dir, "codebase_index_report.txt"),
            "implementation_report_path": os.path.join(paper_dir, "code_implementation_report.txt"),
            "workspace_dir": workspace_dir,
        }

    async def _document_preprocessing_agent(self, dir_info: Dict[str, str]) -> Dict[str, Any]:
        try:
            logger.info("🔍 启动自适应文档预处理流程...")
            paper_dir = dir_info["paper_dir"]
            logger.info(f"   论文目录: {paper_dir}")

            # 步骤1：检查Markdown文件是否存在
            md_file_list = [f for f in os.listdir(paper_dir) if f.endswith(".md")]

            if not md_file_list:
                logger.info("ℹ️ 未发现Markdown文件，跳过文档预处理")
                dir_info["segments_ready"] = False
                dir_info["use_segmentation"] = False
                return {
                    "status": "skipped",
                    "reason": "no_markdown_files",
                    "paper_dir": paper_dir,
                    "segments_ready": False,
                    "use_segmentation": False,
                }

            # 步骤2：读取文档内容并校验文件类型
            primary_md_path = os.path.join(paper_dir, md_file_list[0])
            doc_content = ""
            try:
                # 校验文件是否为PDF（避免扩展名错误）
                with open(primary_md_path, "rb") as f:
                    file_header = f.read(8)
                    if file_header.startswith(b"%PDF"):
                        raise IOError(
                            f"文件 {primary_md_path} 实际为PDF格式，非文本文件。请转换为Markdown格式或使用PDF处理工具。"
                        )

                # 读取Markdown文件内容
                with open(primary_md_path, "r", encoding="utf-8") as f:
                    doc_content = f.read()
            except Exception as content_read_err:
                logger.error(f"⚠️ 读取文档内容失败: {content_read_err}")
                dir_info["segments_ready"] = False
                dir_info["use_segmentation"] = False
                return {
                    "status": "error",
                    "error_message": f"文档读取失败: {str(content_read_err)}",
                    "paper_dir": paper_dir,
                    "segments_ready": False,
                    "use_segmentation": False,
                }

            # 步骤3：判断是否需要执行文档分割
            need_segment, segment_reason = self._should_use_document_segmentation(doc_content)
            logger.info(f"📊 分割决策结果: {need_segment}")
            logger.info(f"   决策依据: {segment_reason}")

            # 存储分割决策结果到目录信息字典
            dir_info["use_segmentation"] = need_segment

            if need_segment:
                logger.info("🔧 启用智能文档分割工作流...")

                # 执行文档分割处理
                segment_process_result = await self._prepare_document_segments(paper_dir=paper_dir)

                if segment_process_result["status"] == "success":
                    logger.info("✅ 文档分割处理完成！")
                    segment_dir = segment_process_result["segments_dir"]
                    logger.info(f"   分割文件存储目录: {segment_dir}")
                    logger.info("   🧠 智能分割结果已就绪，可供给规划代理使用")

                    # 存储分割信息到目录信息字典
                    dir_info["segments_dir"] = segment_dir
                    dir_info["segments_ready"] = True

                    return segment_process_result

                else:
                    segment_err_msg = segment_process_result.get("error_message", "未知错误")
                    logger.warning(f"⚠️ 文档分割处理失败: {segment_err_msg}")
                    logger.warning("   降级为传统全文档处理模式...")
                    dir_info["segments_ready"] = False
                    dir_info["use_segmentation"] = False

                    return {
                        "status": "fallback_to_traditional",
                        "original_error": segment_err_msg,
                        "paper_dir": paper_dir,
                        "segments_ready": False,
                        "use_segmentation": False,
                        "fallback_reason": "segmentation_failed",
                    }
            else:
                logger.info("📖 启用传统全文档读取工作流...")
                dir_info["segments_ready"] = False

                return {
                    "status": "traditional",
                    "reason": segment_reason,
                    "paper_dir": paper_dir,
                    "segments_ready": False,
                    "use_segmentation": False,
                    "document_size": len(doc_content),
                }

        except Exception as proc_err:
            logger.error(f"❌ 文档预处理流程发生错误: {proc_err}")
            logger.info("   继续执行传统全文档处理模式...")

            # 确保降级处理的参数设置
            dir_info["segments_ready"] = False
            dir_info["use_segmentation"] = False

            return {
                "status": "error",
                "paper_dir": dir_info["paper_dir"],
                "segments_ready": False,
                "use_segmentation": False,
                "error_message": str(proc_err),
            }

    def _should_use_document_segmentation(self,
        document_content: str, config_path: str = "E:\test-agentcore-deepcode\examples\deepcode_agent\mcp_agent.config.yaml"
    ) -> Tuple[bool, str]:
        # 读取并解析分割配置
        default_config = {"enabled": True, "size_threshold_chars": 50000}
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}  # 处理空配置文件
                seg_config = config.get("document_segmentation", {})
                # 合并配置与默认值
                seg_config = {
                    "enabled": seg_config.get("enabled", default_config["enabled"]),
                    "size_threshold_chars": seg_config.get("size_threshold_chars", default_config["size_threshold_chars"])
                }
            else:
                logger.info(f"📄 Config file {config_path} not found, using default segmentation settings")
                seg_config = default_config
        except Exception as e:
            logger.error(f"📄 Error reading segmentation config from {config_path}: {e}")
            logger.info("📄 Using default segmentation settings")
            seg_config = default_config

        # 判断是否启用分割
        if not seg_config["enabled"]:
            return False, "Document segmentation disabled in configuration"

        doc_size = len(document_content)
        threshold = seg_config["size_threshold_chars"]

        if doc_size > threshold:
            return (
                True,
                f"Document size ({doc_size:,} chars) exceeds threshold ({threshold:,} chars)",
            )
        else:
            return (
                False,
                f"Document size ({doc_size:,} chars) below threshold ({threshold:,} chars)",
            )

    async def _prepare_document_segments(
            self,
            paper_dir: str,
            force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        准备文档分割段，执行文档分析、分割质量验证并返回处理结果

        Args:
            paper_dir: 论文目录路径
            force_refresh: 是否强制刷新缓存（默认False）

        Returns:
            Dict[str, Any]: 包含处理状态、路径及结果摘要的字典
        """
        try:
            # 第一步：文档分析与准备
            logger.info(f"Starting document analysis for: {paper_dir}")
            # 检查Markdown文件是否存在
            markdown_files = [file for file in os.listdir(paper_dir) if file.endswith(".md")]
            if not markdown_files:
                raise ValueError(f"No markdown file found in {paper_dir}")

            # 构造分析提示并调用LLM
            doc_analysis_prompt = ANALYZE_AND_PREPARE_DOCUMENT_USER_PROMPT.format(
                paper_dir=paper_dir,
                force_refresh=force_refresh,
                paper_dir_2=paper_dir
            )
            doc_analysis_output = await self.document_segmentation_agent.ainvoke({"query": doc_analysis_prompt})
            logger.info("Document analysis completed successfully")

            # 第二步：获取文档概览
            doc_overview_prompt = GET_DOCUMENT_OVERVIEW_USER_PROMPT.format(paper_dir=paper_dir)
            doc_overview_output = await self.document_segmentation_agent.ainvoke({"query": doc_overview_prompt})
            doc_overview_data = {
                "status": "success",
                "paper_dir": paper_dir,
                "overview_result": doc_overview_output
            }

            # 第三步：验证分割质量
            seg_validate_prompt = VALIDATE_SEGMENTATION_QUALITY_USER_PROMPT.format(paper_dir=paper_dir)
            seg_validate_output = await self.document_segmentation_agent.ainvoke({"query": seg_validate_prompt})

            # 整合所有结果返回
            segments_dir = os.path.join(paper_dir, "document_segments")
            return {
                "status": "success",
                "paper_dir": paper_dir,
                "segments_dir": segments_dir,
                "analysis_result": doc_analysis_output,
                "segments_available": True,
                "overview_data": doc_overview_data,
                "validation_result": seg_validate_output
            }

        except Exception as e:
            error_details = str(e)
            logger.error(f"Error in document processing pipeline: {error_details}")
            # 统一错误返回格式，包含各步骤可能的错误标识
            return {
                "status": "error",
                "paper_dir": paper_dir,
                "error_message": error_details,
                "segments_available": False,
                "overview_data": None,
                "validation_result": None
            }
        
    def _get_default_search_server(self, config_path: str = "E:\\test-agentcore-deepcode\\examples\\deepcode_agent\\mcp_agent.config.yaml") -> str:
        """
        从配置文件获取默认搜索服务
        """
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                
                default_server = config.get("default_search_server", "brave")
                logger.info(f"🔍 Using search server: {default_server}")
                return default_server
            else:
                return "brave"
        except Exception as e:
            logger.warning(f"⚠️ Error reading search config: {e}, using default: brave")
            return "brave"

    def _get_server_names(self) -> List[str]:
        """获取所有需要的 MCP Server 列表"""
        search_server = self._get_default_search_server()
        # 包含文件系统和搜索服务
        return ["filesystem", search_server]   
    
    async def _orchestrate_code_planning(self, dir_info: Dict[str, str]):
        """
        代码规划流程：
        检查现有计划 -> 准备上下文 -> 执行多智能体分析 -> 保存结果
        """
        logger.info("🏗️ Phase 4: Synthesizing intelligent code architecture...")
        
        initial_plan_path = dir_info["initial_plan_path"]
        paper_dir = dir_info["paper_dir"]
        
        # 获取预处理阶段（Phase 3.5）的决策结果
        use_segmentation = dir_info.get("use_segmentation", True)
        logger.info(f"📊 Planning strategy: {'Segmented Mode (RAG-like)' if use_segmentation else 'Traditional Mode (Full-Context)'}")

        # 1. 幂等性检查：如果已有计划，跳过
        if os.path.exists(initial_plan_path):
            logger.info(f"✅ Found existing plan at {initial_plan_path}, skipping generation.")
            return

        # 2. 执行核心分析工作流
        try:
            # 调用工作流函数
            plan_content = await self._run_code_analyzer_workflow(
                paper_dir, use_segmentation
            )
            
            # 3. 保存生成结果
            if plan_content:
                with open(initial_plan_path, "w", encoding="utf-8") as f:
                    f.write(plan_content)
                logger.info(f"💾 Initial plan saved to {initial_plan_path}")
                
                # 可选：打印预览
                preview = plan_content[:200].replace('\n', ' ')
                logger.info(f"📝 Plan preview: {preview}...")
            else:
                logger.error("❌ Generated plan is empty, file not saved.")
                raise ValueError("Code planning returned empty result")
            
        except Exception as e:
            logger.error(f"❌ Error in code planning orchestration: {e}")
            raise e
        
    def _get_file_size_threshold(self, config_path: str = "E:\\test-agentcore-deepcode\\examples\\deepcode_agent\\mcp_agent.config.yaml") -> int:
        """
        负责读取配置中的文件大小阈值
        """
        default_threshold = 50000
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                
                # 优先读取配置文件
                return config.get("document_segmentation", {}).get("size_threshold_chars", default_threshold)
            else:
                return default_threshold
        except Exception as e:
            # 记录 debug 日志即可，不中断流程
            logger.debug(f"Config read error: {e}, using default threshold.")
            return default_threshold
        
    async def _run_code_analyzer_workflow(self, paper_dir: str, use_segmentation: bool = True) -> str:
        """
        执行代码分析工作流：
        1. 动态读取配置 (Token限制 & 文件阈值)。
        2. 智能构建上下文 (避免 Context Overflow)。
        3. 执行聚合 Agent 并应用自适应重试策略。
        """
        # 获取 Token 限制
        base_token_limit, retry_token_limit = get_token_limits() 
        
        # 获取文件大小阈值
        file_size_threshold = self._get_file_size_threshold()
        logger.info(f"⚙️ Dynamic Config: BaseToken={base_token_limit}, RetryToken={retry_token_limit}, FileThreshold={file_size_threshold}")
        search_server = self._get_default_search_server()
        full_content_loaded = False
        # 2. 智能上下文构建 (Context Preparation)
        context_instruction = ""
        
        if use_segmentation:
            # 模式 A: 分段模式 (Segmentation Mode)
            # 不读取全文，指示 Agent 读取 document_segments 目录
            logger.info("🔧 Context Strategy: Using document segments (Segmentation Mode).")
            segments_dir = os.path.join(paper_dir, "document_segments")
            
            # 检查分段目录是否存在且不为空
            if os.path.exists(segments_dir) and os.listdir(segments_dir):
                context_instruction = (
                    f"The research paper is extensive. Instead of raw text, I have prepared structured summaries "
                    f"in the directory: '{segments_dir}'.\n"
                    f"**Action Required**: Use your tools to read the files in this segments directory to understand the system architecture and algorithms."
                )
            else:
                logger.warning(f"⚠️ Segments directory empty or missing at {segments_dir}, falling back to manual read.")
                context_instruction = f"Please use your tools to analyze the paper files located in: {paper_dir}"
        else:
            # 模式 B: 传统模式 (Traditional Mode)
            # 尝试读取全文，但受 file_size_threshold 保护
            logger.info("📖 Context Strategy: Attempting to load full document content.")
            try:
                paper_content = ""
                found_md = False
                for filename in os.listdir(paper_dir):
                    if filename.endswith(".md"):
                        file_path = os.path.join(paper_dir, filename)
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                            if len(content) < file_size_threshold: 
                                paper_content = content
                                context_instruction = (
                                    f"Here is the full content of the research paper:\n"
                                    f"=== PAPER CONTENT START ===\n"
                                    f"{paper_content}\n"
                                    f"=== PAPER CONTENT END ===\n"
                                )
                                logger.info(f"📄 Loaded {len(content)} chars into context window.")
                                full_content_loaded = True  # <--- 标记: 全文已加载
                            else:
                                logger.warning(f"⚠️ File too large (> {file_size_threshold} chars) for direct context. Falling back to tool-use.")
                                context_instruction = (
                                    f"The paper file is located at: {file_path}.\n"
                                    f"It is too large ({len(content)} chars) to display directly in this prompt.\n"
                                    f"**Action Required**: Please read it using your file system tools."
                                )
                                full_content_loaded = False  # <--- 标记: 未加载全文
                        found_md = True
                        break
                
                if not found_md:
                    context_instruction = f"Please locate and analyze the research paper in directory: {paper_dir}"
                    
            except Exception as e:
                full_content_loaded = False
                logger.warning(f"⚠️ Failed to read paper content directly: {e}")
                context_instruction = f"Please locate and analyze the research paper in directory: {paper_dir}"
        
        # 构建最终提示词
        # 1. 定义搜索指令
        search_directive = (
            "🔍 **Verification Protocol**: \n"
            "You have access to external search tools (Brave). You MUST use them to:\n"
            " - Verify specific library versions (e.g., ensure PyTorch/TensorFlow compatibility).\n"
            " - Find official repositories or reference implementations.\n"
            " - Clarify ambiguous algorithmic details.\n"
            "Do NOT hallucinate API calls or library names."
        )

        # 2. 构建主指令
        base_query = (
            f"Project Workspace Directory: {paper_dir}\n\n"
            f"=== RESEARCH CONTEXT ===\n"
            f"{context_instruction}\n"
            f"=== END CONTEXT ===\n\n"
            f"{search_directive}\n\n"
            f"**Mission**: Synthesize the research analysis into a concrete, production-ready "
            f"code reproduction blueprint in strict YAML format.\n\n"
            f"**Structure Requirement**: The output must contain exactly these keys:\n"
            f"- file_structure\n"
            f"- implementation_components\n"
            f"- environment_setup\n"
            f"- validation_approach\n"
            f"- implementation_strategy"
        )

        # 构建 Tool Filter
        current_tool_filter = {}
        if use_segmentation:
            current_tool_filter = None # None 表示允许所有已注册工具 (Search + Filesystem)
        
        elif full_content_loaded:
            # 传统模式且全文已注入 Prompt：
            # 禁止使用 filesystem 工具，防止 Agent 浪费 Token 去重复读取文件
            # 只允许使用搜索工具
            logger.info(f"🔒 Optimization: Full content loaded. Disabling filesystem tools, allowing only {search_server}.")
            current_tool_filter = {
                search_server: None,  # 允许该 server 下的所有工具
                "filesystem": []      # 空列表 = 禁止该 server 下的所有工具
            }
        else:
            # 传统模式但没读取到全文
            # 允许 Agent 使用文件系统自己去读
            logger.info("🔓 Context missing. Enabling filesystem access for agents.")
            current_tool_filter = {
                search_server: None,
                "filesystem": ["read_text_file", "list_directory"] # 只开放必要的读权限
            }

        # 3. 执行聚合与重试 (Execution & Adaptive Retry Loop)
        current_max_tokens = base_token_limit
        current_temp = 0.2
        max_attempts = 3
        best_result = ""

        for attempt in range(max_attempts):
            try:
                logger.info(f"🚀 Planning execution attempt {attempt + 1}/{max_attempts}")
                logger.debug(f"   Params: max_tokens={current_max_tokens}, temp={current_temp:.2f}")

                # 构造运行时参数
                runtime_options = {
                    "llm_config": {
                        "max_tokens": current_max_tokens,
                        "temperature": current_temp,
                        "tool_filter": current_tool_filter
                    }
                }

                # 调用聚合 Agent
                response = await self.planning_engine.ainvoke(
                    inputs={"query": base_query}, 
                    runtime=runtime_options
                )
                
                # 兼容返回格式
                plan_text = response.get("content", "") if isinstance(response, dict) else str(response)
                integrity_score = self.evaluate_plan_completeness(plan_text)
                
                if integrity_score >= 0.8:
                    logger.info(f"✅ High-quality plan generated (Score: {integrity_score:.2f})")
                    return plan_text
                
                # 自适应参数调整 (Strategy: Reduce Output to fit Input)
                logger.warning(f"⚠️ Plan incomplete (Score: {integrity_score:.2f}). Triggering retry strategy...")
                
                # 更新 best_result 兜底
                if len(plan_text) > len(best_result):
                    best_result = plan_text
                
                # 参数调整逻辑
                if attempt == 0:
                    # 如果 Base 失败，说明 Context 溢出，必须减少 Output 预留
                    current_max_tokens = retry_token_limit
                elif attempt == 1:
                    # 第2次尝试先降到 90%
                    current_max_tokens = int(retry_token_limit * 0.9)
                else:
                    # 后续重试在 Retry 基础上继续衰减 
                    current_max_tokens = int(retry_token_limit * 0.8)

                # 稍微降低温度以求稳
                current_temp = max(current_temp - 0.15, 0.05)

            except Exception as e:
                logger.error(f"❌ Execution failed at attempt {attempt + 1}: {e}")
                # 遇到异常也继续尝试重试，直到次数用尽
                continue

        logger.warning("⚠️ Max retries reached without perfect result. Returning best available plan.")
        # 如果 best_result 依然为空，抛出异常中断流程
        if not best_result:
            raise ValueError("Failed to generate code plan after multiple attempts.")
            
        return best_result
    
    def evaluate_plan_completeness(self,
        content: str
    ) -> float:
        """
        评估 LLM 生成的 YAML 计划书的完整性和质量。
        
        Args:
            content (str): LLM 生成的原始文本


        Returns:
            float: 完整性评分 (0.0 - 1.0)
        """
        # 定义默认的必需章节常量
        DEFAULT_PLAN_SECTIONS = [
            "file_structure:",
            "implementation_components:",
            "validation_approach:",
            "environment_setup:",
            "implementation_strategy:",
        ]
        # 0. 快速失败检查：内容过短直接返回 0
        if not content or len(content.strip()) < 500:
            if logger:
                logger.debug("Plan validation failed: Content too short (<500 chars).")
            return 0.0

        # 初始化配置
        keys_to_check = DEFAULT_PLAN_SECTIONS
        text_lower = content.lower()
        total_score = 0.0
        
        # 定义权重配置 (总和 1.0)
        weights = {
            "sections": 0.5,      # 核心章节覆盖率
            "structure": 0.2,     # YAML 格式标记
            "completeness": 0.15, # 结尾是否完整
            "length": 0.15        # 内容丰富度
        }

        # 1. 核心章节覆盖率检查 (Weight: 0.5)
        found_count = sum(1 for key in keys_to_check if key in text_lower)
        coverage_ratio = found_count / len(keys_to_check)
        total_score += coverage_ratio * weights["sections"]

        if logger and found_count < len(keys_to_check):
            missing = [k for k in keys_to_check if k not in text_lower]
            logger.debug(f"🔍 Plan validation: Missing sections {missing}")

        # 2. YAML 结构标记检查 (Weight: 0.2)
        # 检查头部标记
        has_start = any(tag in content for tag in ["```yaml", "file_structure:", "paper_info:"])
        # 检查尾部标记 (检查后 500 字符)
        tail_content = content[-500:]
        has_end = any(tag in tail_content for tag in ["```", "validation_approach:", "implementation_strategy:"])

        if has_start and has_end:
            total_score += weights["structure"]
        elif has_start:
            total_score += weights["structure"] / 2  # 只有头没有尾，给一半分

        # 3. 结尾截断检测 (Weight: 0.15)
        lines = content.strip().splitlines()
        is_truncated = True
        
        if lines:
            last_line = lines[-1].strip()
            # 合法结尾特征：
            valid_endings = ("```", ".", ":", "}", "]")
            is_list_item = last_line.startswith(("-", "*"))
            is_short_line = len(last_line) < 80 and not last_line.endswith(",")
            
            if last_line.endswith(valid_endings) or is_list_item or is_short_line:
                is_truncated = False

        if not is_truncated:
            total_score += weights["completeness"]
        elif logger:
            logger.debug(f"⚠️ Plan validation: Possible truncation detected at line: '{lines[-1][-30:]}...'")

        # 4. 内容丰富度 (长度) 检查 (Weight: 0.15)
        length = len(content)
        if length >= 10000:
            total_score += weights["length"]       # 满分0.15 分
        elif length >= 5000:
            total_score += weights["length"] - 0.05 # 0.1 分
        elif length >= 2000:
            total_score += weights["length"]- 0.1 # 0.05分

        return min(total_score, 1.0)
    
    async def _execute_reference_mining_workflow(self, dir_info: Dict[str, str]) -> str:
        """
        执行参考文献挖掘工作流：
        1. 引入了更严格的 Fast Mode (无索引模式) 检查。
        2. 增加了对参考文献文件的预检机制。
        3. 动态构建 Prompt 上下文，而非仅依赖静态 Prompt。
        """
        logger.info("📚 Phase 5: Initiating citation mining and repository discovery...")
        
        reference_path = dir_info["reference_path"]
        paper_dir = dir_info["paper_dir"]

        # 1. 检查是否开启了索引/高级模式
        if not self.enable_index:
            logger.info("⚡ Fast Mode active: Skipping advanced citation analysis.")
            skip_msg = "Citation mining skipped due to Fast Mode configuration."
            
            # 创建占位文件以保持流水线完整性
            with open(reference_path, "w", encoding="utf-8") as f:
                f.write(skip_msg)
            return skip_msg

        # 2. 缓存检查 (幂等性设计)
        if os.path.exists(reference_path):
            try:
                with open(reference_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()
                if len(existing_content) > 50: # 简单的有效性检查
                    logger.info(f"✅ Loaded existing reference analysis from {reference_path}")
                    return existing_content
            except Exception as e:
                logger.warning(f"⚠️ Failed to read cache, re-running analysis: {e}")

        # 3. 执行挖掘逻辑
        try:
            # 动态构建任务指令，改变 LLM 输入特征
            mining_query = (
                f"Target Directory: {paper_dir}\n"
                f"**Task**: Locate the markdown file of the research paper in the target directory. "
                f"Analyze the 'References' or 'Bibliography' section specifically.\n"
                f"**Goal**: Identify and extract the 5 most relevant references that explicitly contain GitHub repository URLs.\n"
                f"**Requirement**: Use your filesystem tools to read the paper. Use search tools if URLs need validation."
            )

            # 调用 Agent
            # 使用 temp=0.2 降低幻觉，保证提取 URL 的准确性
            # 此处复用了 self.citation_miner (即 CitationDiscoverySpecialist)
            mining_result = await self.citation_miner.ainvoke(
                {"query": mining_query}
            )
            
            # 提取内容
            result_content = mining_result.get("content", "") if isinstance(mining_result, dict) else str(mining_result)

            # 4. 结果持久化
            if result_content:
                with open(reference_path, "w", encoding="utf-8") as f:
                    f.write(result_content)
                logger.info(f"💾 Reference analysis saved to {reference_path}")
            else:
                logger.warning("⚠️ Citation miner returned empty result.")

            return result_content

        except Exception as e:
            logger.error(f"❌ Error during reference mining workflow: {e}")
            # 发生错误时不中断主流程，而是写入错误日志供后续步骤参考
            error_log = f"Error during mining: {str(e)}"
            with open(reference_path, "w", encoding="utf-8") as f:
                f.write(error_log)
            return error_log
    async def _execute_repo_acquisition_workflow(
        self, 
        reference_data: str, 
        dir_map: Dict[str, str]
    ) -> None:
        """
        [Phase 6 Execution] 执行仓库获取工作流
        
        Refactored Logic:
        1. Pre-flight checks (Fast Mode & Data Validity).
        2. Execution with dynamic context.
        3. Post-execution verification.
        """
        logger.info("📦 Phase 6: Automating external repository acquisition...")
        
        download_log = dir_map["download_path"]
        code_base_dir = os.path.join(dir_map["paper_dir"], "code_base")

        # --- Check 1: Fast Mode 熔断 ---
        if not self.enable_index:
            msg = "⚡ Repository acquisition skipped (Fast Mode enabled)."
            logger.info(msg)
            self._write_log(download_log, msg)
            return

        # --- Check 2: 引用数据健康检查 ---
        # 如果 Phase 5 失败或返回了空数据，不要启动 Agent 浪费 Token
        if not reference_data or len(reference_data) < 20 or "skipped" in reference_data.lower():
            msg = "⚠️ Reference data is invalid or empty. Skipping download phase."
            logger.warning(msg)
            self._write_log(download_log, msg)
            return

        try:
            # 给文件系统一点缓冲时间
            await asyncio.sleep(2)

            # --- Execution: 动态构建指令 ---
            # 明确告诉 Agent 目标路径，这是原版代码中隐含在 Prompt 里的
            acquisition_instruction = (
                f"Reference Context:\n{reference_data}\n\n"
                f"**Task**: Clone the relevant GitHub repositories listed above.\n"
                f"**Target Directory**: {code_base_dir}\n"
                f"**Constraint**: Use the 'github-downloader' tool. If a repo already exists, skip it."
            )

            # 调用 Agent
            # 使用较低的 temperature (0.1) 保证工具调用的准确性
            agent_response = await self.repo_acquisitor.ainvoke(
                {"query": acquisition_instruction},
                runtime={"llm_config": {"max_tokens": 4096, "temperature": 0.1}}
            )
            
            result_text = agent_response.get("content", "") if isinstance(agent_response, dict) else str(agent_response)

            # 记录执行日志
            self._write_log(download_log, result_text)
            logger.info(f"💾 Acquisition logs saved to {download_log}")

            # --- Validation: 独立验证逻辑 ---
            self._verify_download_results(code_base_dir)

        except Exception as e:
            err_msg = f"❌ Error in repo acquisition: {str(e)}"
            logger.error(err_msg)
            self._write_log(download_log, err_msg)
            # 即使下载失败，也不中断主流程，抛出警告即可
            # raise e  <-- 注释掉 raise，让流程继续走到 Phase 7

    def _verify_download_results(self, target_dir: str) -> bool:
        """
        [Phase 6 Validation] 验证下载是否真正成功
        """
        if not os.path.exists(target_dir):
            logger.warning(f"⚠️ Target directory not created: {target_dir}")
            return False

        # 扫描目录下是否有非隐藏文件夹
        try:
            repos = [d for d in os.listdir(target_dir) 
                    if os.path.isdir(os.path.join(target_dir, d)) and not d.startswith(".")]
            
            if repos:
                logger.info(f"✅ Download verified: {len(repos)} repositories found ({', '.join(repos[:3])}...)")
                return True
            else:
                logger.warning("⚠️ 'code_base' exists but appears empty. Agent may have failed to clone.")
                return False
        except Exception:
            return False

    def _write_log(self, path: str, content: str):
        """辅助写入方法"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to write log to {path}: {e}")