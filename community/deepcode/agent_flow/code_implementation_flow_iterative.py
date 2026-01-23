#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
"""
Code Implementation Flow - Iterative Dialogue Architecture

采用迭代对话模式，LLM 自主决策实现流程：
- LLM Decision: LLM 完全控制实现节奏和顺序
- Tool Execution: Controller 被动执行工具调用
- Feedback Loop: 每次工具调用后提供详细反馈
- Memory Optimization: 基于 Token 计数的智能内存管理

流程特点：
1. LLM 驱动：Agent 自主决定下一步行动
2. 工具反馈：每次工具调用后生成引导性反馈
3. 进度跟踪：实时跟踪文件实现进度
4. 循环检测：防止陷入无效的分析循环
5. 内存压缩：自动触发对话历史压缩
"""

import asyncio
import os
import time
import re 
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from openjiuwen.core.common.logging import logger
from examples.deepcode_agent.agents import ReActAgent, AgentConfig
from openjiuwen.core.utils.tool.mcp.base import ToolServerConfig
from mcp import StdioServerParameters
from examples.deepcode_agent.prompts.sys_prompts import (
    PURE_CODE_IMPLEMENTATION_SYSTEM_PROMPT_INDEX,
)
from openjiuwen.core.context_engine.engine import ContextEngine
from openjiuwen.core.context_engine.config import ContextEngineConfig
from openjiuwen.core.utils.llm.messages import BaseMessage

load_dotenv()


# ============================================================
# Part 1: Progress Tracking Agent 
# ============================================================

class Plan:
    """
    文件实现进度跟踪器
    
    职责：
    - 跟踪已实现的文件列表
    - 检测分析循环（只读不写）
    - 管理技术决策记录
    - 提供进度统计
    """
    
    # 支持的文件扩展名（代码、配置、文档）
    TRACKED_EXTENSIONS = {
        # 代码文件
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java",
        ".c", ".cpp", ".h", ".hpp", ".cc", ".cxx",
        ".go", ".rs", ".php", ".rb", ".pl", ".lua",
        ".r", ".kt", ".scala", ".vue",
        # 前端文件
        ".html", ".css", ".scss", ".sass", ".less",
        # 配置文件
        ".json", ".yaml", ".yml", ".toml", ".xml",
        ".ini", ".cfg", ".env",
        # 文档文件
        ".md", ".rst", ".txt",
        # 脚本文件
        ".sh", ".bash", ".zsh", ".bat", ".ps1", ".cmd",
        # 数据库和其他
        ".sql", ".db", ".dockerfile", ".gitignore",
        ".lock", ".sum", ".mod"
    }
    
    # 排除的文件扩展名（图片等）
    EXCLUDED_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
        ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar"
    }
    
    # 排除的目录模式
    EXCLUDED_DIRECTORIES = {
        "__pycache__", ".pyc", "node_modules", ".git",
        ".vscode", ".idea", "dist", "build", "output",
        ".egg-info", "venv", ".venv", "env", ".env",
        "target", "bin", "obj", ".next", ".nuxt"
    }
    
    def __init__(self, mcp_agent, allow_read_ops: bool = True):
        """
        初始化进度跟踪器
        
        Args:
            mcp_agent: MCP agent 实例
            allow_read_ops: 是否允许读取操作工具
        """
        self.mcp_agent = mcp_agent
        self.allow_read_ops = allow_read_ops
        
        # 实现统计
        self.completed_files: List[Dict[str, Any]] = []
        self.files_count = 0
        self.unique_files: set = set()
        self.file_summaries: Dict[str, str] = {}

        # 计划文件列表（从 plan 中提取）
        self.planned_files: List[str] = []
        self.implemented_files: set = set()  # 已实现的规范化文件路径

        # 实现摘要（用于外部接口兼容）
        self.implementation_summary: Dict[str, Any] = {
            "completed_files": self.completed_files  # 指向同一列表，避免重复存储
        }

        # 循环检测
        self.recent_tool_calls: List[str] = []
        self.max_read_streak = 5  # 最多连续5次只读操作
        self.max_read_without_write = 5  # 最多连续几次操作不写入代码

        # 技术记录
        self.tech_decisions: List[Dict] = []
        self.constraints: List[Dict] = []
        self.architecture_notes: List[Dict] = []

    async def process_tool_execution(self, tool_calls: List[Dict]) -> List[Dict]:
        """处理工具执行 调用并跟踪进度"""
        results = []

        # 定义读取类工具
        read_tools = {"read_file", "read_code_mem", "list_files", "list_directory"}

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "unknown")
            tool_input = tool_call.get("input", {})
            tool_call_id = tool_call.get("id", f"call_{len(results)}")  # 获取tool_call_id

            # 提取基础工具名（去除前缀，如 code-implementation-write_file → write_file）
            base_tool_name = tool_name.split("-")[-1] if "-" in tool_name else tool_name

            logger.info(f"[Tracker] Processing tool: {tool_name}")

            # 更新工具模式追踪（P1-6）
            self._track_tool_pattern(base_tool_name)

            try:
                # P0-1: 如果禁用读工具，拒绝所有读操作
                if not self.allow_read_ops and base_tool_name in read_tools:
                    logger.warning(f"[Tracker] 🚫 Read tool '{tool_name}' blocked (allow_read_ops=False)")
                    results.append({
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "content": f"[Access Denied] Read operations are disabled. Please use write_file to implement code directly.",
                        "is_error": False
                    })
                    continue

                # 如果 Agent 想读文件，且我们手里有摘要，就只给它摘要
                if base_tool_name == "read_file":
                    file_path = tool_input.get("file_path") or tool_input.get("path")
                    if file_path and file_path in self.file_summaries:
                        logger.info(f"[Tracker] ⚡ Intercepted read_file for {file_path}, returning summary.")
                        summary = self.file_summaries[file_path]
                        results.append({
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "content": f"[Memory Optimized Content]\nSummary of {file_path}:\n{summary}",
                            "is_error": False
                        })
                        continue

                # 🔧 修复参数名：统一将 path → file_path (MCP 工具严格要求 file_path)
                if base_tool_name == "write_file" and "path" in tool_input and "file_path" not in tool_input:
                    tool_input["file_path"] = tool_input.pop("path")
                    logger.debug(f"[Tracker] ⚙️  Normalized parameter: path → file_path")

                # 执行真实 MCP 工具（使用BaseAgent的execute_mcp_tool方法）
                result = await self.mcp_agent.execute_mcp_tool(
                    tool_name=tool_name,
                    inputs=tool_input
                )

                # 跟踪写入
                if base_tool_name == "write_file":
                    self._track_file_write(tool_input, result)

                results.append({
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "content": str(result),
                    "is_error": False
                })

            except Exception as e:
                logger.error(f"[Tracker] Tool failed: {e}")
                results.append({
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "content": f"Error: {str(e)}",
                    "is_error": True
                })

        return results

    def set_planned_files(self, planned_files: List[str]):
        """设置计划文件列表"""
        self.planned_files = planned_files
        logger.info(f"[Tracker] Set planned files: {len(planned_files)} files")

    def register_file_summary(self, file_path: str, summary: str):
        """注册文件摘要"""
        self.file_summaries[file_path] = summary
        logger.info(f"[Tracker] Registered summary for {file_path}")

    def get_knowledge_base_text(self) -> str:
        """获取当前所有摘要的拼接文本"""
        if not self.file_summaries:
            return "No files implemented yet."

        kb = "## Implemented Files Knowledge Base:\n"
        for path, summary in self.file_summaries.items():
            kb += f"\n### {path}\n{summary}\n"
        return kb

    def _track_file_write(self, tool_input: Dict, result: Any):
        """跟踪文件写入"""
        # 兼容 path 和 file_path 参数
        file_path = tool_input.get("path", "") or tool_input.get("file_path", "")

        if file_path and file_path not in self.unique_files:
            self.files_count += 1
            self.unique_files.add(file_path)

            # 规范化路径并记录到已实现集合
            normalized_path = self._normalize_path(file_path)
            self.implemented_files.add(normalized_path)

            content_length = len(str(tool_input.get("content", "")))

            # 保存详细的文件实现信息
            file_info = {
                "file": file_path,
                "timestamp": time.time(),
                "content_length": content_length,
                "iteration": self.files_count,
                "size": content_length
            }

            self.completed_files.append(file_info)

            logger.info(f"[Tracker] File implemented: {file_path} (Total: {self.files_count})")

    def _track_tool_pattern(self, tool_name: str):
        """跟踪工具调用模式以检测循环"""
        self.recent_tool_calls.append(tool_name)

        # 只保留最近的 N 次调用（使用较大的限制值）
        max_limit = max(self.max_read_streak, self.max_read_without_write)
        if len(self.recent_tool_calls) > max_limit:
            self.recent_tool_calls.pop(0)

        # 检测分析循环
        if len(set(self.recent_tool_calls)) == 1:
            logger.warning("[Tracker] Analysis loop detected")

    def is_stuck_in_analysis(self) -> bool:
        """
        检测是否陷入分析循环

        Returns:
            True 如果连续多次只读不写
        """
        # 检查最近的调用是否都是读取类工具
        read_tools = {"read_file", "read_code_mem", "list_files", "list_directory", "search_code_references"}

        # 只取最近的 max_read_streak 个调用进行检查
        recent_tools_slice = self.recent_tool_calls[-self.max_read_streak:]
        if len(recent_tools_slice) >= self.max_read_streak:
            recent_set = set(recent_tools_slice)
            is_stuck = recent_set.issubset(read_tools) and len(recent_set) >= 1

            if is_stuck:
                logger.warning(f"[Tracker] Analysis loop detected: {recent_tools_slice}")
            return is_stuck

        return False

    def _normalize_path(self, file_path: str) -> str:
        """规范化文件路径（提取文件名和相对路径）"""
        # 移除前导斜杠和反斜杠
        normalized = file_path.replace("\\", "/").strip("/")
        # 转换为小写以进行不区分大小写的匹配
        return normalized.lower()

    def _fuzzy_match_file(self, target_file: str, implemented_file: str) -> bool:
        """模糊匹配文件路径"""
        # 提取文件名
        target_name = target_file.split("/")[-1]
        impl_name = implemented_file.split("/")[-1]

        # 规则1: 文件名完全匹配（最常见情况）
        if target_name == impl_name:
            return True

        # 规则2: 完整路径匹配或包含关系
        if target_file in implemented_file or implemented_file in target_file:
            return True

        # 规则3: 路径后缀匹配（例如：data/preprocessor.py 匹配 src/data/preprocessor.py）
        if implemented_file.endswith(target_file) or target_file.endswith(implemented_file):
            return True

        return False

    def check_implementation_complete(self) -> tuple[bool, List[str]]:
        """
        检查是否所有计划文件都已实现

        Returns:
            (is_complete, unimplemented_files)
        """
        if not self.planned_files:
            # 如果没有设置计划文件列表，则无法验证
            logger.warning("[Tracker] No planned files set, cannot verify completion")
            return False, []

        # 规范化计划文件列表
        normalized_planned = [self._normalize_path(f) for f in self.planned_files]

        # 查找未实现的文件
        unimplemented = []
        for planned_file in normalized_planned:
            # 检查是否有匹配的实现文件
            matched = False
            for impl_file in self.implemented_files:
                if self._fuzzy_match_file(planned_file, impl_file):
                    matched = True
                    break

            if not matched:
                unimplemented.append(planned_file)

        is_complete = len(unimplemented) == 0

        if is_complete:
            logger.info(f"[Tracker] ✅ All {len(normalized_planned)} planned files implemented!")
        else:
            logger.info(f"[Tracker] ⏳ Progress: {len(self.implemented_files)}/{len(normalized_planned)} files")
            logger.info(f"[Tracker] Unimplemented: {unimplemented[:5]}..." if len(unimplemented) > 5 else f"[Tracker] Unimplemented: {unimplemented}")

        return is_complete, unimplemented

    def scan_generated_files(self, output_dir: str) -> set:
        """
        扫描输出目录中实际生成的所有文件

        Args:
            output_dir: 输出目录路径

        Returns:
            规范化后的文件路径集合
        """
        generated_files = set()

        if not os.path.exists(output_dir):
            logger.warning(f"[Tracker] Output directory not found: {output_dir}")
            return generated_files

        # 递归扫描所有支持的文件类型
        for root, dirs, files in os.walk(output_dir):
            # 跳过排除的目录
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRECTORIES]

            for file in files:
                # 检查文件扩展名
                file_ext = "." + file.split(".")[-1] if "." in file else ""

                # 跳过排除的文件类型
                if file_ext in self.EXCLUDED_EXTENSIONS:
                    continue

                # 只处理跟踪的文件类型
                if file_ext in self.TRACKED_EXTENSIONS or file in [".gitignore", "Dockerfile"]:
                    # 构建相对路径
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, output_dir)

                    # 规范化路径
                    normalized = self._normalize_path(rel_path)
                    generated_files.add(normalized)

        logger.info(f"[Tracker] Scanned {len(generated_files)} files in output directory")
        if generated_files:
            logger.debug(f"[Tracker] Sample generated files: {list(generated_files)[:5]}")

        return generated_files

    def check_completion_by_directory_scan(self, output_dir: str) -> tuple[bool, List[str], int]:
        """
        通过扫描目录检查实现完成度（最可靠的方法）

        Args:
            output_dir: 输出目录路径

        Returns:
            (is_complete, unimplemented_files, generated_count)
        """
        if not self.planned_files:
            logger.warning("[Tracker] No planned files set, cannot verify completion")
            return False, [], 0

        # 扫描实际生成的文件
        generated_files = self.scan_generated_files(output_dir)

        # 规范化计划文件列表
        normalized_planned = [self._normalize_path(f) for f in self.planned_files]

        # 查找未实现的文件
        unimplemented = []
        matched_count = 0

        for planned_file in normalized_planned:
            matched = False
            for generated_file in generated_files:
                if self._fuzzy_match_file(planned_file, generated_file):
                    matched = True
                    matched_count += 1
                    logger.debug(f"[Tracker] ✅ Matched: {planned_file} ≈ {generated_file}")
                    break

            if not matched:
                unimplemented.append(planned_file)
                logger.debug(f"[Tracker] ❌ Not found: {planned_file}")

        is_complete = len(unimplemented) == 0

        if is_complete:
            logger.info(f"[Tracker] ✅ All {len(normalized_planned)} planned files found in directory!")
        else:
            logger.info(f"[Tracker] 📊 Directory scan: {matched_count}/{len(normalized_planned)} files matched")
            logger.info(f"[Tracker] Missing files: {unimplemented[:5]}..." if len(unimplemented) > 5 else f"[Tracker] Missing: {unimplemented}")

        return is_complete, unimplemented, len(generated_files)

    def get_loop_break_guidance(self) -> str:
        """获取打破分析循环的引导"""
        # 只取最近的 max_read_streak 个调用进行显示
        recent_tools_slice = self.recent_tool_calls[-self.max_read_streak:]
        return f"""🚨 **ANALYSIS LOOP DETECTED - ACTION REQUIRED**

**Problem**: You've been analyzing files for {len(recent_tools_slice)} consecutive operations without writing code.
**Recent operations**: {' → '.join(recent_tools_slice)}

**SOLUTION - IMPLEMENT CODE NOW**:
1. **STOP ANALYZING** - You have enough information
2. **Use write_file** to create a new code file
3. **Choose ANY file** from the plan that hasn't been implemented
4. **Write complete code** - don't ask for permission

**Files implemented so far**: {self.files_count}
**Your goal**: Implement MORE files, not analyze existing ones!

**CRITICAL**: Your next response MUST use write_file!"""

    def get_statistics(self) -> Dict[str, Any]:
        """获取进度统计"""
        return {
            "total_files": self.files_count,
            "unique_files_count": len(self.unique_files),
            "files_implemented_count": self.files_count,
            "completed_files": [f["file"] for f in self.completed_files],
            "recent_tool_pattern": self.recent_tool_calls,
            "tech_decisions_count": len(self.tech_decisions),
            "is_stuck": self.is_stuck_in_analysis(),
            "completed_files_list": [f["file"] for f in self.completed_files]
        }

    def get_completed_files_list(self) -> List[str]:
        """获取已完成文件列表"""
        return [f["file"] for f in self.implementation_summary["completed_files"]]

    def reset_tracking(self):
        """重置跟踪状态"""
        self.completed_files = []
        self.files_count = 0
        self.unique_files = set()
        self.recent_tool_calls = []
        self.implemented_files = set()
        # self.implementation_summary["completed_files"] 会自动指向新的 self.completed_files 列表
        logger.info("[Tracker] Progress tracking reset")


# ============================================================
# Part 2: Memory Management (对话历史压缩)
# ============================================================

class DialogueMemoryManager:
    """
    对话历史内存管理器（集成 ContextEngine + 原版 Deepcode 逻辑）
    
    职责：
    - 基于 write_file 和消息数量的对话压缩（原版逻辑）
    - 保留关键上下文（初始计划、未实现文件、本轮工具结果）
    - 清理冗余信息
    - 使用 ContextEngine 进行结构化存储
    """
    
    def __init__(self, agent_id: str = "iterative_code_agent", progress_tracker=None):
        """
        初始化内存管理器
        
        Args:
            agent_id: Agent ID（用于 ContextEngine）
            progress_tracker: 进度跟踪器（用于获取未实现文件列表）
        """
        self.compression_count = 0
        self.progress_tracker = progress_tracker
        
        # 本轮工具结果缓存（用于压缩时保留）
        self.current_round_tool_results: List[Dict] = []
        
        # write_file 执行标志（用于触发主动压缩）
        self.last_write_file_success: bool = False
        
        # 初始化 ContextEngine
        self.context_engine = ContextEngine(
            agent_id=agent_id,
            config=ContextEngineConfig(conversation_history_length=200)
        )
        self.session_id = f"session_{int(time.time())}"
        self.agent_context = self.context_engine.get_agent_context(self.session_id)
        
    def _convert_to_base_message(self, msg_dict: Dict) -> BaseMessage:
        """
        将字典格式消息转换为 BaseMessage
        
        Args:
            msg_dict: 字典格式的消息 {"role": "user/assistant", "content": "..."}
            
        Returns:
            BaseMessage 对象
        """
        return BaseMessage(
            role=msg_dict.get("role", "user"),
            content=msg_dict.get("content", "")
        )
    
    def _convert_to_dict(self, base_msg: BaseMessage) -> Dict:
        """
        将 BaseMessage 转换回字典格式
        
        Args:
            base_msg: BaseMessage 对象
            
        Returns:
            字典格式消息
        """
        return {
            "role": base_msg.role,
            "content": base_msg.content
        }
    
    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量
        
        Args:
            text: 输入文本
            
        Returns:
            估算的 token 数量（粗略：字符数 / 4）
        """
        # 简单估算：英文约4字符=1token，中文约2字符=1token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return (chinese_chars // 2) + (other_chars // 4)
    
    def estimate_messages_tokens(self, messages: List[Dict]) -> int:
        """
        估算消息列表的总 token 数
        
        Args:
            messages: 消息列表
            
        Returns:
            总 token 数
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += self.estimate_tokens(str(content))
        return total
    
    def should_trigger_memory_optimization(self, messages: List[Dict], files_implemented_count: int) -> bool:
        """
        【原版 Deepcode】检查是否应该触发主动内存优化
        
        触发条件：
        检测到 write_file 成功执行（通过标志位，而非字符串匹配）
        
        Args:
            messages: 当前消息列表（保留参数兼容性）
            files_implemented_count: 已实现文件数量
            
        Returns:
            True 如果应该触发压缩
        """
        # 使用标志位检测，避免不可靠的字符串匹配
        if self.last_write_file_success:
            logger.info("[Memory] ✅ write_file success detected, triggering optimization")
            return True
        
        return False
    
    def should_trigger_emergency_compression(self, messages: List[Dict]) -> bool:
        """
        【原版 Deepcode】检查是否需要紧急压缩（被动触发）
        
        触发条件：消息数量 > 50
        
        Args:
            messages: 当前消息列表
            
        Returns:
            True 如果需要紧急压缩
        """
        return len(messages) > 50
    
    def apply_memory_optimization(
        self,
        system_message: str,
        messages: List[Dict],
        files_implemented_count: int
    ) -> List[Dict]:
        """
        【原版 Deepcode】应用内存优化 - 精简消息历史
        
        保留策略（与原版一致）：
        1. System prompt（更新版本，包含进度摘要）
        2. 初始计划（第二条用户消息）
        3. 未实现文件列表
        4. 实现进度摘要
        5. 本轮工具结果
        
        Args:
            system_message: 原始 system prompt
            messages: 原始消息列表
            files_implemented_count: 已实现文件数量
            
        Returns:
            压缩后的消息列表
        """
        if len(messages) < 2:
            return messages
        
        # 1. 提取未实现文件列表
        unimplemented = self._get_unimplemented_files()
        
        # 2. 生成实现进度摘要
        progress_summary = self._generate_progress_summary(files_implemented_count)
        
        # 3. 提取初始计划（通常是第一或第二条用户消息）
        initial_plan = ""
        for msg in messages[:3]:  # 在前3条消息中查找
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # 检查是否包含计划特征
                if "Code Reproduction Plan" in content or "file_structure" in content.lower():
                    initial_plan = content
                    break
        
        if not initial_plan and len(messages) > 1:
            # 降级：使用第二条消息
            initial_plan = messages[1].get("content", "")
        
        # 4. 获取本轮工具结果
        tool_results_text = self._get_current_round_tool_results()
        
        # 5. 获取知识库（已实现文件的接口摘要）
        knowledge_base = self._get_knowledge_base()
        
        # 6. 构建压缩后的消息列表
        new_messages = [
            {
                "role": "system",
                "content": f"{system_message}\n\n{progress_summary}"
            },
            {
                "role": "user",
                "content": f"""{initial_plan}

**当前未实现文件:**
{unimplemented}

{knowledge_base}

**本轮工具执行结果:**
{tool_results_text}

**下一步行动:**
Continue implementing the remaining files from the plan above.
Use write_file to create the next file.
"""
            }
        ]
        
        self.compression_count += 1
        
        # 更新 ContextEngine：创建新会话以清空历史
        self.session_id = f"session_{int(time.time())}"
        self.agent_context = self.context_engine.get_agent_context(self.session_id)
        # 添加新的精简历史
        base_messages = [self._convert_to_base_message(msg) for msg in new_messages]
        self.agent_context.batch_add_messages(base_messages)
        
        logger.info(
            f"[Memory] 🧹 Memory optimized! Compressed {len(messages)} → {len(new_messages)} messages "
            f"(removed {len(messages) - len(new_messages)})"
        )
        
        return new_messages
    
    def _get_unimplemented_files(self) -> str:
        """
        获取未实现文件列表
        
        Returns:
            未实现文件的格式化字符串
        """
        if not self.progress_tracker:
            return "Unable to determine (tracker not available)"
        
        # 使用跟踪器的检查方法
        is_complete, unimplemented = self.progress_tracker.check_implementation_complete()
        
        if is_complete:
            return "✅ All planned files have been implemented!"
        
        if not unimplemented:
            return "No planned files information available"
        
        # 格式化文件列表
        file_list = "\n".join([f"  - {f}" for f in unimplemented[:20]])  # 最多显示20个
        if len(unimplemented) > 20:
            file_list += f"\n  ... and {len(unimplemented) - 20} more files"
        
        return f"Total: {len(unimplemented)} files remaining\n{file_list}"
    
    def _generate_progress_summary(self, files_count: int) -> str:
        """
        生成实现进度摘要
        
        Args:
            files_count: 已实现文件数量
            
        Returns:
            进度摘要字符串
        """
        if not self.progress_tracker:
            return f"**Implementation Progress:** {files_count} files completed"
        
        total_planned = len(self.progress_tracker.planned_files) if self.progress_tracker.planned_files else 0
        
        if total_planned > 0:
            percentage = (files_count / total_planned) * 100
            return (
                f"**Implementation Progress:** {files_count}/{total_planned} files completed ({percentage:.1f}%)\n"
                f"**Status:** Keep implementing remaining files from the plan"
            )
        else:
            return f"**Implementation Progress:** {files_count} files completed"
    
    def _get_current_round_tool_results(self) -> str:
        """
        获取本轮工具执行结果
        
        Returns:
            工具结果的格式化字符串
        """
        if not self.current_round_tool_results:
            return "No tool results in this round"
        
        results_text = []
        for i, result in enumerate(self.current_round_tool_results, 1):
            tool_name = result.get("tool_name", "unknown")
            content = result.get("content", "")
            # 截断过长的内容
            if len(content) > 500:
                content = content[:500] + "...[truncated]"
            results_text.append(f"{i}. {tool_name}: {content}")
        
        return "\n".join(results_text)
    
    def _get_knowledge_base(self) -> str:
        """
        🔧 [关键修复] 获取知识库（已实现文件的接口摘要）
        
        这是原版 Deepcode 的核心机制：
        - 在压缩后的 Prompt 中注入所有已实现文件的接口摘要
        - 让 LLM 在"失忆"后仍然知道已有代码的类和函数
        - 避免重复调用 read_file
        
        Returns:
            知识库的格式化字符串
        """
        if not self.progress_tracker:
            return ""
        
        # 从 Plan 获取所有文件摘要
        file_summaries = self.progress_tracker.file_summaries
        
        if not file_summaries:
            return "**Knowledge Base:** No files implemented yet."
        
        # 构建知识库文本
        kb_parts = ["**Below is the Knowledge Base of Implemented Files:**"]
        kb_parts.append("(Use this to understand existing code structure without calling read_file)\n")
        
        for file_path, summary in file_summaries.items():
            kb_parts.append(f"### 📄 {file_path}")
            kb_parts.append(f"```\n{summary}\n```\n")
        
        kb_text = "\n".join(kb_parts)
        
        # 统计信息
        total_chars = sum(len(s) for s in file_summaries.values())
        logger.info(f"[Memory] 📚 Knowledge Base injected: {len(file_summaries)} files, {total_chars:,} chars")
        
        return kb_text
    
    def record_tool_result(self, tool_name: str, content: str):
        """
        记录工具执行结果（用于压缩时保留）
        
        Args:
            tool_name: 工具名称
            content: 工具结果内容
        """
        self.current_round_tool_results.append({
            "tool_name": tool_name,
            "content": content
        })
        
        # 只保留最近5个工具结果
        if len(self.current_round_tool_results) > 5:
            self.current_round_tool_results = self.current_round_tool_results[-5:]
    
    def clear_tool_results(self):
        """
        清空本轮工具结果（压缩后调用）
        """
        self.current_round_tool_results = []
        # 重置 write_file 标志
        self.last_write_file_success = False
    
    def mark_write_file_success(self):
        """
        标记 write_file 成功执行（由主循环调用）
        """
        self.last_write_file_success = True
    
    def get_stored_messages(self, num: int = -1) -> List[Dict]:
        """
        从 ContextEngine 获取存储的消息
        
        Args:
            num: 获取的消息数量（-1 表示全部）
            
        Returns:
            字典格式的消息列表
        """
        base_messages = self.agent_context.get_messages(num)
        return [self._convert_to_dict(msg) for msg in base_messages]
    
    def store_message(self, message: Dict):
        """
        存储单条消息到 ContextEngine
        
        Args:
            message: 字典格式的消息
        """
        base_msg = self._convert_to_base_message(message)
        self.agent_context.add_message(base_msg)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取压缩统计"""
        stored_count = len(self.agent_context.get_messages(-1))
        return {
            "total_compressions": self.compression_count,
            "stored_messages_count": stored_count,
            "context_engine_enabled": True
        }


# ============================================================
# Part 3: JSON Repair Utility (JSON 修复工具)
# ============================================================

class AdvancedJsonRepairer:
    """
    高级 JSON 修复工具
    
    职责：
    - 修复截断的 JSON 字符串
    - 智能补全缺失的括号
    - 处理特定工具的必需字段
    """
    
    @staticmethod
    def fix_malformed_json(json_text: str, tool_identifier: str = "") -> Dict:
        """
        修复损坏的 JSON 字符串
        
        Args:
            json_text: 待修复的 JSON 文本
            tool_identifier: 工具名称（用于特定修复逻辑）
            
        Returns:
            解析后的字典
        """
        import json
        
        # Step 1: 基础清理
        cleaned = json_text.strip()
        
        # 移除尾随逗号
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # Step 2: 智能补全括号
        repaired = AdvancedJsonRepairer._auto_close_brackets(cleaned)
        
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass
        
        # Step 3: 工具特定修复
        if tool_identifier == "write_file":
            return AdvancedJsonRepairer._fix_write_file_json(repaired)
        
        # 最后尝试：返回基础结构
        return {"error": "JSON parsing failed", "raw_content": json_text}
    
    @staticmethod
    def _auto_close_brackets(text: str) -> str:
        """
        自动闭合未闭合的括号和引号
        """
        # 统计括号数量
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        quote_count = text.count('"')
        
        result = text
        
        # 闭合字符串
        if quote_count % 2 != 0:
            result += '"'
        
        # 闭合数组和对象
        result += ']' * open_brackets
        result += '}' * open_braces
        
        return result
    
    @staticmethod
    def _fix_write_file_json(text: str) -> Dict:
        """
        针对 write_file 工具的特殊修复
        """
        import json
        
        try:
            data = json.loads(text)
        except:
            data = {}
        
        # 确保必需字段存在
        if "path" not in data:
            # 尝试从文本中提取路径
            path_match = re.search(r'"path"\s*:\s*"([^"]+)"', text)
            if path_match:
                data["path"] = path_match.group(1)
            else:
                data["path"] = "unknown.py"
        
        if "content" not in data:
            # 尝试提取内容
            content_match = re.search(r'"content"\s*:\s*"([^"]+)', text, re.DOTALL)
            if content_match:
                data["content"] = content_match.group(1)
            else:
                data["content"] = "# Content extraction failed"
        
        return data


# ============================================================
# Part 4: Feedback Generator (用户反馈生成器)
# ============================================================

class IterativeFeedbackGenerator:
    """
    迭代反馈生成器
    
    职责：
    - 生成成功反馈
    - 生成错误引导
    - 生成无工具调用警告
    - 编译工具结果和引导
    """
    
    @staticmethod
    def generate_success_feedback(files_count: int) -> str:
        """生成成功实现后的反馈"""
        return f"""✅ **File implementation completed successfully!**

📊 **Progress Status:** {files_count} files implemented

🎯 **Next Action:** Check if ALL files from the reproduction plan are implemented.

⚡ **Decision Process:**
1. **If ALL files are implemented:** 
   - Use `execute_python` or `execute_bash` to test the complete implementation
   - Then respond "**implementation complete**" to end the conversation
   
2. **If MORE files need implementation:** Continue with dependency-aware workflow:
   - **Start with `read_code_mem`** to understand existing implementations and dependencies
   - **Optionally use `search_code_references`** for reference patterns (OPTIONAL - use for inspiration only, original paper specs take priority)
   - **Then `write_file`** to implement the new component
   - **Finally: Test** if needed

💡 **Key Point:** Always verify completion status before continuing with new file creation."""
    
    @staticmethod
    def generate_error_feedback() -> str:
        """生成错误处理反馈"""
        return """❌ **Error Detected During Implementation**

🔧 **Action Required:**
1. **Review** the error details above carefully
2. **Fix** the identified issue in your implementation
3. **Check completion status:**
   - If all files are done: Test and say "**implementation complete**"
   - If more files needed: Continue with proper implementation
4. **Ensure** proper error handling in future code

💡 **Remember:** Fix the error and continue systematically."""
    
    @staticmethod
    def generate_no_tools_warning(files_count: int) -> str:
        """生成无工具调用警告"""
        return f"""⚠️ **No Tool Calls Detected!**

📊 **Current Progress:** {files_count} files implemented

🚨 **Action Required:** You MUST use tools to make progress!

⚡ **Decision Process:**
1. **Check completion status first:**
   - If ALL files are done: Test with `execute_python`/`execute_bash`, then say "**implementation complete**"
   - If MORE files needed: Use `write_file` to implement next component

2. **Use tools, not just explanations!**
   - `write_file`: Create/update code files
   - `search_code_references`: Find reference implementations (optional)

🚨 **Critical:** Your next response MUST include tool calls!"""
    
    @staticmethod
    def compile_feedback(tool_results: List[Dict], guidance: str) -> str:
        """
        编译工具结果和引导为完整反馈
        
        Args:
            tool_results: 工具执行结果列表
            guidance: 引导文本
            
        Returns:
            完整的用户反馈消息
        """
        feedback_parts = []
        
        # 添加工具执行结果
        if tool_results:
            feedback_parts.append("## 🔧 Tool Execution Results:\n")
            
            for result in tool_results:
                tool_name = result.get("tool_name", "unknown")
                content = result.get("content", "")
                is_error = result.get("is_error", False)
                
                status_icon = "❌" if is_error else "✅"
                feedback_parts.append(f"### {status_icon} {tool_name}")
                feedback_parts.append(f"```\n{content}\n```\n")
        
        # 添加引导文本
        if guidance:
            feedback_parts.append(guidance)
        
        return "\n\n".join(feedback_parts)
    
    @staticmethod
    def check_for_errors(tool_results: List[Dict]) -> bool:
        """
        检查工具结果中是否有错误
        
        Args:
            tool_results: 工具执行结果列表
            
        Returns:
            True 如果检测到错误
        """
        for result in tool_results:
            if result.get("is_error", False):
                return True
            
            content = str(result.get("content", "")).lower()
            if "error" in content or "failed" in content or "exception" in content:
                return True
        
        return False


# ============================================================
# Part 5: Tool Filter (工具过滤器)
# ============================================================

class EssentialToolFilter:
    """
    核心工具过滤器
    
    职责：
    - 过滤 MCP 工具，只保留核心工具
    - 避免工具泛滥导致 LLM 混淆
    """
    
    # 定义核心工具集
    CORE_TOOLS = {"write_file", "search_code_references"}
    
    @staticmethod
    def filter_tool_definitions(all_tools: List, logger_instance) -> List:
        """
        过滤工具定义，只保留核心工具
        
        Args:
            all_tools: 所有可用工具列表（McpToolInfo 对象列表）
            logger_instance: 日志记录器
            
        Returns:
            过滤后的工具列表
        """
        # DEBUG: 打印所有工具名称
        tool_names = []
        for t in all_tools:
            if hasattr(t, 'name'):
                tool_names.append(t.name)
            else:
                tool_names.append(t.get('name', 'unknown'))
        logger_instance.info(f"🔍 All registered tools: {tool_names}")
        logger_instance.info(f"🔍 CORE_TOOLS filter: {EssentialToolFilter.CORE_TOOLS}")
        
        filtered = []
        for tool in all_tools:
            # 兼容字典格式和对象格式
            if hasattr(tool, 'name'):
                tool_name = tool.name  # McpToolInfo 对象
            else:
                tool_name = tool.get("name", "")  # 字典格式
            
            # 匹配基础名称或带前缀的名称（如 code-implementation-write_file）
            base_name = tool_name.split("-")[-1] if tool_name else ""  # 提取最后一部分
            
            match_result = (base_name in EssentialToolFilter.CORE_TOOLS or tool_name in EssentialToolFilter.CORE_TOOLS)
            logger_instance.info(f"🔍 Check {tool_name}: base={base_name}, match={match_result}")
            
            if match_result:
                filtered.append(tool)
        
        # 提取工具名称用于日志（兼容两种格式）
        def get_tool_name(t):
            return t.name if hasattr(t, 'name') else t.get('name', 'unknown')
        
        logger_instance.info(
            f"🔧 Tool filtering applied: {len(filtered)}/{len(all_tools)} tools active"
        )
        logger_instance.info(
            f"   Active tools: {[get_tool_name(t) for t in filtered]}"
        )
        
        return filtered


# ============================================================
# Part 6: Iterative Controller (迭代控制器)
# ============================================================

class IterativeCodeFlow:
    """
    迭代式代码实现流程控制器
    
    核心特点：
    - LLM 完全自主决策
    - 工具调用反馈循环
    - 智能进度跟踪
    - 循环检测与打破
    - 内存自动压缩
    """
    
    def __init__(self):
        """初始化迭代控制器"""
        self._llm_config = {
            "model_provider": os.getenv("LLM_MODEL_PROVIDER"),
            "api_key": os.getenv("LLM_API_KEY"),
            "api_base": os.getenv("LLM_API_BASE"),
            "model_name": os.getenv("LLM_MODEL_NAME"),
        }
        
        self._agent: Optional[ReActAgent] = None
        self._progress_tracker: Optional[Plan] = None
        self._memory_manager: Optional[DialogueMemoryManager] = None
        self._feedback_generator = IterativeFeedbackGenerator()
        self._json_repairer = AdvancedJsonRepairer()
        self._allow_read_ops: bool = True  # 默认允许读操作
        
        # 完成声明计数器（容错机制）
        self._completion_claim_count: int = 0
        self._max_completion_claims: int = 5  # 允许最多5次完成声明
        
        # 输出目录（用于扫描实际生成的文件）
        self._output_dir: Optional[str] = None
    
    async def initialize(self):
        """初始化 Agent 和工具"""
        logger.info("[IterativeFlow] Initializing agent and tools...")
        
        # 初始化 ReActAgent
        self._agent = ReActAgent(
            AgentConfig(
                name="IterativeCodeAgent",
                llm_config=self._llm_config,
                system_prompt=PURE_CODE_IMPLEMENTATION_SYSTEM_PROMPT_INDEX,
            )
        )
        
        # 加载 MCP 工具
        mcp_servers = []
        
        # 代码实现工具
        impl_path = os.getenv("CODE_IMPLEMENTATION_SERVER_PATH")
        if impl_path and os.path.exists(impl_path):
            mcp_servers.append(ToolServerConfig(
                server_name="code-implementation",
                params=StdioServerParameters(command="python", args=[impl_path]),
                client_type="stdio"
            ))
        
        # 代码参考索引工具
        ref_path = os.getenv("CODE_REFERENCE_INDEXER_PATH")
        if ref_path and os.path.exists(ref_path):
            mcp_servers.append(ToolServerConfig(
                server_name="code-reference",
                params=StdioServerParameters(command="python", args=[ref_path]),
                client_type="stdio"
            ))
        
        if mcp_servers:
            await self._agent.add_mcps(mcp_servers)
            
            # 暂时禁用工具过滤，让所有工具都可用（调试用）
            # TODO: 修复工具过滤逻辑后重新启用
            if hasattr(self._agent, '_tool_infos') and self._agent._tool_infos:
                tool_count = len(self._agent._tool_infos)
                logger.info(f"[IterativeFlow] All {tool_count} tools are active (filtering disabled)")
        
        # 初始化进度跟踪器（传递读工具配置）
        self._progress_tracker = Plan(
            self._agent,
            allow_read_ops=self._allow_read_ops
        )
        
        # 初始化内存管理器（传递 progress_tracker 引用）
        self._memory_manager = DialogueMemoryManager(
            agent_id="iterative_code_agent",
            progress_tracker=self._progress_tracker
        )
        
        # 日志读工具状态
        read_status = "ENABLED" if self._allow_read_ops else "DISABLED"
        logger.info(f"[IterativeFlow] Read tools: {read_status}")
        logger.info("[IterativeFlow] Agent initialized successfully")
    
    async def execute(
        self,
        plan_file_path: str,
        target_directory: Optional[str] = None,
        enable_read_tools: bool = True,
    ) -> Dict[str, Any]:
        """
        执行迭代式代码实现流程
        
        Args:
            plan_file_path: 实现计划文件路径
            target_directory: 目标目录（可选）
            enable_read_tools: 是否启用读取工具（默认 True）
            
        Returns:
            执行结果字典
        """
        # 保存读工具配置
        self._allow_read_ops = enable_read_tools
        
        # 重置完成声明计数器
        self._completion_claim_count = 0
        
        start_time = time.time()
        
        try:
            # 读取计划
            plan_content = Path(plan_file_path).read_text(encoding='utf-8')
            base_dir = target_directory or str(Path(plan_file_path).parent)
            output_dir = os.path.join(base_dir, "generate_code")
            
            # 保存输出目录供后续使用
            self._output_dir = output_dir
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            logger.info("=" * 60)
            logger.info("[IterativeFlow] Starting Iterative Implementation")
            logger.info(f"  Plan: {plan_file_path}")
            logger.info(f"  Output: {output_dir}")
            logger.info("=" * 60)
            
            # 设置工作空间
            await self._set_workspace(output_dir)
            
            # 提取计划文件列表
            planned_files = self._extract_files_from_plan(plan_content)
            self._progress_tracker.set_planned_files(planned_files)
            
            # 构建初始消息
            initial_message = self._build_initial_prompt(plan_content, output_dir)
            
            # 执行迭代循环
            result = await self._iterative_loop(initial_message)
            
            # 生成最终报告
            elapsed = time.time() - start_time
            stats = self._progress_tracker.get_statistics()
            
            return {
                "status": "success",
                "output_directory": output_dir,
                "statistics": stats,
                "duration_seconds": round(elapsed, 2),
                "result": result
            }
            
        except Exception as e:
            logger.error(f"[IterativeFlow] Execution failed: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            # 确保清理 MCP 资源
            await self._cleanup_resources()
    
    async def _iterative_loop(self, initial_message: str) -> str:
        """核心迭代循环 (修正版 - 使用完整消息历史)"""
        max_iterations = 800
        max_time = 7200  
        
        iteration = 0
        start_time = time.time()
        
        # 构建完整的消息历史（包含system prompt）
        from openjiuwen.core.utils.llm.messages import SystemMessage, HumanMessage
        messages = [
            SystemMessage(content=self._agent.system_prompt),
            HumanMessage(content=initial_message)
        ]
        
        logger.info(f"[IterativeFlow] Starting iteration loop (max: {max_iterations})")
        
        while iteration < max_iterations:
            iteration += 1
            elapsed = time.time() - start_time
            
            if elapsed > max_time:
                logger.warning(f"[IterativeFlow] Max time ({max_time}s) reached")
                break
            
            logger.info(f"[IterativeFlow] Iteration {iteration}/{max_iterations}")
            
            # 1. 调用 LLM（传递完整消息历史 + 工具定义）- 带重试机制
            max_retries = 3
            retry_delay = 1  # 初始延迟（秒）
            response = None
            
            for retry_attempt in range(max_retries):
                try:
                    # 使用 call_llm 而非 ainvoke，以传递完整消息历史
                    response = self._agent.call_llm(
                        self._agent.model_name,
                        messages,
                        self._agent._tool_infos  # 传递工具定义
                    )
                    # 成功则跳出重试循环
                    break
                except Exception as e:
                    retry_attempt_display = retry_attempt + 1
                    if retry_attempt_display < max_retries:
                        logger.warning(
                            f"[IterativeFlow] LLM call failed (attempt {retry_attempt_display}/{max_retries}): {e}"
                        )
                        logger.info(f"[IterativeFlow] Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                    else:
                        # 所有重试都失败
                        logger.error(
                            f"[IterativeFlow] LLM call failed after {max_retries} attempts: {e}"
                        )
                        # 退出主循环
                        break
            
            # 如果所有重试都失败，response 仍为 None
            if response is None:
                logger.error("[IterativeFlow] Failed to get LLM response, exiting iteration loop")
                break
            
            # 提取响应内容和工具调用
            response_text = response.content if hasattr(response, 'content') else str(response)
            tool_calls_raw = response.tool_calls if hasattr(response, 'tool_calls') else []
            
            if not response_text: 
                response_text = "[Empty response]"
            
            # 添加AI响应到消息历史
            from openjiuwen.core.utils.llm.messages import AIMessage
            messages.append(AIMessage(content=response_text, tool_calls=tool_calls_raw))
            # P1-5: 同步消息到 ContextEngine
            self._memory_manager.store_message({"role": "assistant", "content": response_text})
            
            if self._check_completion_signal(response_text):
                logger.info("[IterativeFlow] Implementation complete signal detected")
                break
            
            # 转换工具调用为字典格式用于执行
            tool_calls = []
            if tool_calls_raw:
                for tc in tool_calls_raw:
                    try:
                        # 尝试使用 JSON 修复工具处理可能的格式问题
                        if isinstance(tc.arguments, str):
                            try:
                                # 首先尝试标准 JSON 解析
                                tool_input = json.loads(tc.arguments)
                            except json.JSONDecodeError:
                                # 解析失败时使用高级修复工具
                                logger.warning(f"[IterativeFlow] JSON parsing failed, attempting repair for {tc.name}")
                                tool_input = AdvancedJsonRepairer.fix_malformed_json(tc.arguments, tc.name)
                        else:
                            tool_input = tc.arguments
                    except Exception as e:
                        # 所有解析方法都失败时，使用默认空字典并记录错误
                        logger.error(f"[IterativeFlow] Failed to parse tool arguments for {tc.name}: {e}")
                        tool_input = {}
                    
                    tool_calls.append({
                        "id": getattr(tc, 'id', f"call_{len(tool_calls)}"),
                        "name": tc.name,
                        "input": tool_input
                    })
            
            # 2. 处理工具调用与内存管理
            if tool_calls:
                # 执行工具 (Tracker 内部处理 read_file 拦截)
                tool_results = await self._progress_tracker.process_tool_execution(tool_calls)
                
                # 记录工具结果到内存管理器（用于压缩时保留）
                for result in tool_results:
                    self._memory_manager.record_tool_result(
                        tool_name=result.get("tool_name", "unknown"),
                        content=result.get("content", "")
                    )
                
                # --- [核心修改] 检测写入并生成真实摘要 ---
                write_success = False
                last_written_file = None
                
                for i, call in enumerate(tool_calls):
                    # 检查是否是成功的 write_file 调用
                    if call.get("name") == "write_file" and not tool_results[i].get("is_error"):
                        write_success = True
                        # 标记 write_file 成功（用于触发主动压缩）
                        self._memory_manager.mark_write_file_success()
                        
                        # 兼容 path 和 file_path 参数
                        last_written_file = call.get("input", {}).get("file_path") or call.get("input", {}).get("path")
                        content = call.get("input", {}).get("content", "")
                        
                        # [修正] 调用 LLM 生成真实的语义摘要
                        if last_written_file and content:
                            logger.info(f"[Flow] Generating summary for {last_written_file}...")
                            summary = await self._generate_summary_with_llm(last_written_file, content)
                            # 存入 Tracker (前提：Plan 已更新)
                            self._progress_tracker.register_file_summary(last_written_file, summary)
                
                # 生成用户反馈
                has_errors = self._feedback_generator.check_for_errors(tool_results)
                if has_errors:
                    guidance = self._feedback_generator.generate_error_feedback()
                else:
                    files_count = self._progress_tracker.files_count
                    guidance = self._feedback_generator.generate_success_feedback(files_count)
                
                user_feedback = self._feedback_generator.compile_feedback(tool_results, guidance)
                # 添加用户反馈到消息历史（添加工具消息）
                from openjiuwen.core.utils.llm.messages import ToolMessage, HumanMessage
                # 先添加所有工具结果
                for result in tool_results:
                    tool_msg = ToolMessage(
                        tool_call_id=result.get("tool_call_id", ""),
                        content=result.get("content", "")
                    )
                    messages.append(tool_msg)
                # 然后添加用户引导反馈
                messages.append(HumanMessage(content=user_feedback))
                # 同步消息到 ContextEngine
                self._memory_manager.store_message({"role": "user", "content": user_feedback})
                
                # --- [核心修改] 原版 Deepcode 内存管理策略 ---
                messages_dict = self._convert_messages_to_dict(messages)
                files_count = self._progress_tracker.files_count
                
                # 检查主动压缩触发条件（检测 write_file）
                if self._memory_manager.should_trigger_memory_optimization(messages_dict, files_count):
                    # 策略 A: 主动压缩（write_file 后）
                    logger.info("[Flow] 🔍 write_file detected, triggering memory optimization")
                    current_system_message = self._agent.system_prompt
                    messages_dict = self._memory_manager.apply_memory_optimization(
                        current_system_message, messages_dict, files_count
                    )
                    messages = self._convert_dict_to_messages(messages_dict)
                    # 清空工具结果缓存（已被压缩到新上下文中）
                    self._memory_manager.clear_tool_results()
                
                # 检查被动压缩触发条件（消息数 > 50）
                elif self._memory_manager.should_trigger_emergency_compression(messages_dict):
                    # 策略 B: 被动压缩（紧急压缩）
                    logger.warning("[Flow] ⚠️ Emergency compression triggered (messages > 50)")
                    current_system_message = self._agent.system_prompt
                    messages_dict = self._memory_manager.apply_memory_optimization(
                        current_system_message, messages_dict, files_count
                    )
                    messages = self._convert_dict_to_messages(messages_dict)
                    # 清空工具结果缓存
                    self._memory_manager.clear_tool_results()
                    
            else:
                # 无工具调用
                files_count = self._progress_tracker.files_count
                warning = self._feedback_generator.generate_no_tools_warning(files_count)
                from openjiuwen.core.utils.llm.messages import HumanMessage
                messages.append(HumanMessage(content=warning))
                # 同步消息到 ContextEngine
                self._memory_manager.store_message({"role": "user", "content": warning})
                
                # 无工具时也检查一下是否需要紧急压缩（防止纯对话撑爆内存）
                messages_dict = self._convert_messages_to_dict(messages)
                if self._memory_manager.should_trigger_emergency_compression(messages_dict):
                    logger.warning("[Flow] ⚠️ Emergency compression triggered (no tools, messages > 50)")
                    current_system_message = self._agent.system_prompt
                    files_count = self._progress_tracker.files_count
                    messages_dict = self._memory_manager.apply_memory_optimization(
                        current_system_message, messages_dict, files_count
                    )
                    messages = self._convert_dict_to_messages(messages_dict)
                    self._memory_manager.clear_tool_results()
            
            # 检测分析循环
            if self._progress_tracker.is_stuck_in_analysis():
                loop_guidance = self._progress_tracker.get_loop_break_guidance()
                from openjiuwen.core.utils.llm.messages import HumanMessage
                messages.append(HumanMessage(content=loop_guidance))
                # P1-5: 同步消息到 ContextEngine
                self._memory_manager.store_message({"role": "user", "content": loop_guidance})
            
            # 每轮结束时通过目录扫描检查实现进度（最可靠的方法）
            if self._output_dir:
                is_complete, unimplemented, generated_count = self._progress_tracker.check_completion_by_directory_scan(self._output_dir)
                
                # 如果目录扫描显示已完成所有文件，提前终止
                if is_complete:
                    logger.info(f"[IterativeFlow] 🎉 Early termination: All {generated_count} planned files detected in directory!")
                    break
                
                # 如果还有未实现的文件，每5轮提供进度提醒
                if iteration % 5 == 0 and unimplemented and len(unimplemented) > 0:
                    progress_reminder = self._generate_progress_reminder(unimplemented)
                    from openjiuwen.core.utils.llm.messages import HumanMessage
                    messages.append(HumanMessage(content=progress_reminder))
                    self._memory_manager.store_message({"role": "user", "content": progress_reminder})
            else:
                # 降级：使用跟踪器检查（每5轮）
                if iteration % 5 == 0:
                    is_complete, unimplemented = self._progress_tracker.check_implementation_complete()
                    if is_complete:
                        logger.info("[IterativeFlow] 🎉 Early termination: All tracked files implemented!")
                        break
                    
                    if unimplemented and len(unimplemented) > 0:
                        progress_reminder = self._generate_progress_reminder(unimplemented)
                        from openjiuwen.core.utils.llm.messages import HumanMessage
                        messages.append(HumanMessage(content=progress_reminder))
                        self._memory_manager.store_message({"role": "user", "content": progress_reminder})
            
        return self._generate_final_report(iteration, time.time() - start_time)
    async def _generate_summary_with_llm(self, file_path: str, content: str) -> str:
        """
        [新增] 调用 LLM 为代码文件生成接口摘要
        用于 Write-and-Forget 策略中的知识库维护
        """
        # 截断过长的代码，避免消耗过多 Token 用于生成摘要
        max_len = 12000
        if len(content) > max_len:
            content_snippet = content[:max_len] + "\n... (truncated)"
        else:
            content_snippet = content

        prompt = f"""You are a code analysis engine. 
Target File: {file_path}

Please analyze the code below and generate a concise "Interface Summary".
The summary MUST include:
1. Class names and their responsibilities.
2. Public function signatures (names, args, return types) and brief explanations.
3. Key global constants.
4. DO NOT include internal implementation details.

Code Content:
```python
{content_snippet}
```

Output the summary directly."""

        max_retries = 3
        retry_delay = 1  # 初始延迟（秒）
        
        for retry_attempt in range(max_retries):
            try:
                # P1-4: 使用BaseAgent的call_llm方法（不传tools参数避免工具调用）
                if hasattr(self._agent, 'call_llm'):
                    # 构造纯文本消息（使用字典格式）
                    messages = [{"role": "user", "content": prompt}]
                    # 调用LLM不传tools参数，避免触发工具调用
                    llm_response = self._agent.call_llm(
                        self._agent.model_name, 
                        messages, 
                        tools=None  # 关键：不传工具避免ReAct循环
                    )
                    # 提取文本内容
                    if hasattr(llm_response, 'content'):
                        return llm_response.content
                    elif isinstance(llm_response, dict):
                        return llm_response.get('content', str(llm_response))
                    else:
                        return str(llm_response)
                else:
                    # 降级方案：使用简单的提取逻辑
                    logger.warning(f"[Summary] call_llm not available, using fallback extraction for {file_path}")
                    return self._extract_code_summary_fallback(content_snippet, file_path)
                    
            except Exception as e:
                retry_attempt_display = retry_attempt + 1
                if retry_attempt_display < max_retries:
                    logger.warning(
                        f"[Summary] LLM call failed for {file_path} (attempt {retry_attempt_display}/{max_retries}): {e}"
                    )
                    logger.info(f"[Summary] Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    # 所有重试都失败，使用 fallback
                    logger.warning(f"[Summary] Failed to generate summary for {file_path} after {max_retries} attempts: {e}")
                    return self._extract_code_summary_fallback(content_snippet, file_path)
    
    def _extract_code_summary_fallback(self, content: str, file_path: str) -> str:
        """降级方案：简单的代码摘要提取"""
        lines = content.split('\n')
        summary_parts = [f"File: {file_path}"]
        
        # 提取类定义
        for line in lines:
            if line.strip().startswith('class '):
                summary_parts.append(line.strip())
            elif line.strip().startswith('def ') and not line.strip().startswith('def _'):
                summary_parts.append(line.strip())
        
        return '\n'.join(summary_parts[:20])  # 限制最多20行
    
    def _convert_messages_to_dict(self, messages: List) -> List[Dict]:
        """将 BaseMessage 列表转换为字典列表（用于内存管理）"""
        result = []
        for msg in messages:
            if hasattr(msg, 'role') and hasattr(msg, 'content'):
                # BaseMessage 对象
                result.append({
                    "role": msg.role,
                    "content": msg.content
                })
            elif isinstance(msg, dict):
                # 已经是字典
                result.append(msg)
        return result
    
    def _convert_dict_to_messages(self, messages_dict: List[Dict]) -> List:
        """将字典列表转换回 BaseMessage 列表"""
        from openjiuwen.core.utils.llm.messages import SystemMessage, HumanMessage, AIMessage
        result = []
        for msg in messages_dict:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                result.append(SystemMessage(content=content))
            elif role == "user":
                result.append(HumanMessage(content=content))
            elif role == "assistant":
                result.append(AIMessage(content=content))
            else:
                # 默认使用 HumanMessage
                result.append(HumanMessage(content=content))
        return result
    
    def _extract_files_from_plan(self, plan_content: str) -> List[str]:
        """
        从计划文本中提取所有需要实现的文件列表
        
        支持的格式：
        1. file_structure: 块中的文件树
        2. 简单的文件列表（支持多种代码、配置、文档文件）
        
        Args:
            plan_content: 计划文本内容
            
        Returns:
            文件路径列表
        """
        files = []
        
        # 构建文件扩展名匹配模式（支持所有跟踪的文件类型）
        extensions_pattern = "|".join(
            [ext.replace(".", r"\.") for ext in self._progress_tracker.TRACKED_EXTENSIONS]
        )
        
        # 方法1: 提取 file_structure 块中的内容
        file_structure_match = re.search(
            r'file_structure:\s*\|(.*?)(?=\n\n|\n[A-Z]|$)', 
            plan_content, 
            re.DOTALL | re.IGNORECASE
        )
        if file_structure_match:
            structure_text = file_structure_match.group(1)
            # 匹配所有支持的文件类型
            pattern = rf'[│├└─\s]*([\w/._-]+(?:{extensions_pattern}))'
            found_files = re.findall(pattern, structure_text)
            files.extend(found_files)
        
        # 方法2: 直接搜索所有支持的文件类型
        if not files:
            pattern = rf'\b([\w/._-]+(?:{extensions_pattern}))\b'
            found_files = re.findall(pattern, plan_content)
            files.extend(found_files)
        
        # 去重
        unique_files = list(set(files))
        
        # 过滤逻辑
        filtered_files = []
        for f in unique_files:
            # 检查是否在排除的目录中
            if any(excluded_dir in f for excluded_dir in self._progress_tracker.EXCLUDED_DIRECTORIES):
                continue
            
            # 检查是否是排除的扩展名
            file_ext = "." + f.split(".")[-1] if "." in f else ""
            if file_ext in self._progress_tracker.EXCLUDED_EXTENSIONS:
                continue
            
            # 检查是否是 HTTP 链接
            if f.startswith("http://") or f.startswith("https://"):
                continue
            
            filtered_files.append(f)
        
        logger.info(f"[IterativeFlow] Extracted {len(filtered_files)} files from plan")
        if filtered_files:
            # 按文件类型分组统计
            file_types = {}
            for f in filtered_files:
                ext = "." + f.split(".")[-1] if "." in f else "no_ext"
                file_types[ext] = file_types.get(ext, 0) + 1
            
            logger.info(f"[IterativeFlow] File types breakdown: {file_types}")
            logger.info(f"[IterativeFlow] Sample files: {filtered_files[:5]}")
        
        return filtered_files
    
    def _build_initial_prompt(self, plan_content: str, output_dir: str) -> str:
        """构建初始提示"""
        # 计算预期文件数（支持所有文件类型）
        tracked_exts = Plan.TRACKED_EXTENSIONS
        expected_files = len([
            line for line in plan_content.split('\n') 
            if any(ext in line for ext in tracked_exts)
        ])
        
        return f"""**URGENT: Start Writing Code NOW**

**Code Reproduction Plan:**
{plan_content}

**Working Directory:** {output_dir}

**IMMEDIATE ACTION REQUIRED:** 
🚨 Do NOT explore, analyze, or read existing files. START WRITING CODE IMMEDIATELY!

1. **START NOW** with the first file from the plan (typically foundation/utility files)
2. Use `write_file` tool to create complete implementations
3. Move to next file immediately after finishing each one
4. Continue until ALL files in the plan are implemented

**Available Tools:**
- `write_file(file_path, content)`: 🎯 **USE THIS TOOL NOW** - Write code, config, and documentation files
- `search_code_references`: Optional reference lookup (use sparingly)

**Supported File Types:**
- Code: .py, .js, .ts, .java, .go, .rs, .cpp, etc.
- Config: .yaml, .json, .toml, .xml, .env, etc.
- Docs: .md, .rst, .txt
- Scripts: .sh, .bat, .ps1

**⚠️ CRITICAL RULES:**
- **USE EXACT FILE PATHS** from the plan's file_structure (e.g., `src/core/retrieval/embedder.py`, NOT just `embedder.py`)
- NO file exploration (no read_file, get_file_structure, execute_bash for exploration)
- NO analysis paralysis - implement based on plan descriptions
- Each iteration should write at least ONE complete file
- When all {expected_files} files are written, say "**implementation complete**"

**PATH EXAMPLE**: If plan shows `configs/model_config.yaml`, use EXACTLY that path in write_file!

**START WRITING THE FIRST FILE RIGHT NOW! 👇**
"""
    
    def _extract_response_text(self, response: Any) -> str:
        """从响应中提取文本内容"""
        if isinstance(response, dict):
            return response.get("output") or response.get("response") or response.get("content") or str(response)
        elif isinstance(response, str):
            return response
        else:
            return str(response)
    
    def _extract_tool_calls(self, response: Any) -> List[Dict]:
        """从响应中提取工具调用"""
        from openjiuwen.core.utils.llm.messages import AIMessage
        
        if isinstance(response, AIMessage):
            # AIMessage.tool_calls 是 List[ToolCall] 对象，需要转换为字典格式
            tool_calls = response.tool_calls or []
            result = []
            for tc in tool_calls:
                result.append({
                    "id": getattr(tc, "id", f"call_{len(result)}"),
                    "name": tc.name,
                    "input": tc.args if hasattr(tc, "args") else {}
                })
            return result
        elif isinstance(response, dict):
            return response.get("tool_calls", [])
        return []
    
    def _check_completion_signal(self, text: str) -> bool:
        """
        检查完成信号（多层验证 + 容错机制）
        
        验证策略：
        1. 优先：目录扫描 - 检查实际生成的文件
        2. 回退：关键词检测
        3. 容错：多次声明完成后强制接受
        """
        # 方法1: 基于目录扫描验证（最可靠）
        if self._output_dir:
            is_complete, unimplemented, generated_count = self._progress_tracker.check_completion_by_directory_scan(self._output_dir)
            if is_complete:
                logger.info(f"[IterativeFlow] ✅ Completion verified by directory scan: All {generated_count} planned files found")
                self._completion_claim_count = 0  # 重置计数器
                return True
        else:
            # 降级到跟踪器检查
            is_complete, unimplemented = self._progress_tracker.check_implementation_complete()
            if is_complete:
                logger.info("[IterativeFlow] ✅ Completion verified: All planned files implemented")
                self._completion_claim_count = 0
                return True
        
        # 方法2: 关键词检测
        text_lower = text.lower()
        completion_signals = [
            "implementation complete",
            "all files implemented",
            "implementation finished"
        ]
        keyword_match = any(signal in text_lower for signal in completion_signals)
        
        if keyword_match:
            # LLM声称完成，增加计数器
            self._completion_claim_count += 1
            
            if unimplemented:
                logger.warning(
                    f"[IterativeFlow] ⚠️ LLM claims completion (#{self._completion_claim_count}) but {len(unimplemented)} files missing: "
                    f"{unimplemented[:3]}..."
                )
                
                # 方法3: 容错机制 - 多次声明后强制接受
                if self._completion_claim_count >= self._max_completion_claims:
                    logger.warning(
                        f"[IterativeFlow] 🔴 FORCED COMPLETION: LLM claimed completion {self._completion_claim_count} times. "
                        f"Accepting as complete despite {len(unimplemented)} unmatched files."
                    )
                    logger.info(
                        f"[IterativeFlow] 📝 This may indicate: (1) Path matching issues, "
                        f"(2) Files were generated but not tracked correctly, "
                        f"(3) Some planned files are not needed."
                    )
                    if self._output_dir:
                        logger.info(f"[IterativeFlow] 📁 Files found in directory: {generated_count}")
                    else:
                        logger.info(f"[IterativeFlow] 📁 Files tracked: {self._progress_tracker.files_count}")
                    return True
                else:
                    remaining_attempts = self._max_completion_claims - self._completion_claim_count
                    logger.info(
                        f"[IterativeFlow] 🔄 Continuing implementation. "
                        f"Will force-accept after {remaining_attempts} more completion claims."
                    )
                    return False
            else:
                # 文件清单匹配，正常完成
                logger.info("[IterativeFlow] ✅ Completion confirmed by LLM")
                self._completion_claim_count = 0
                return True
        else:
            # 没有完成关键词，重置计数器
            self._completion_claim_count = 0
        
        return False
    
    def _generate_progress_reminder(self, unimplemented_files: List[str]) -> str:
        """生成进度提醒消息"""
        total_planned = len(self._progress_tracker.planned_files)
        implemented_count = len(self._progress_tracker.implemented_files)
        
        # 限制显示的文件数量
        show_count = min(5, len(unimplemented_files))
        sample_files = unimplemented_files[:show_count]
        
        return f"""📊 **Implementation Progress Check**

**Status:** {implemented_count}/{total_planned} files completed ({implemented_count * 100 // total_planned if total_planned > 0 else 0}%)

**Remaining files to implement:** {len(unimplemented_files)}
{chr(10).join([f'  - {f}' for f in sample_files])}
{'  - ...' if len(unimplemented_files) > show_count else ''}

💡 **Reminder:** Please continue implementing the remaining files from the plan."""
    
    async def _set_workspace(self, output_dir: str):
        """设置工作空间"""
        try:
            await self._agent.execute_mcp_tool("code-implementation-set_workspace", {"workspace_path": output_dir})
            logger.info(f"[IterativeFlow] Workspace set: {output_dir}")
        except Exception as e:
            logger.warning(f"[IterativeFlow] Workspace setup failed: {e}")
    
    async def _cleanup_resources(self):
        """清理 MCP 资源（避免异步资源泄漏）"""
        try:
            from openjiuwen.core.runner.runner import resource_mgr
            # 清理工具管理器中的 MCP 连接
            tool_mgr = resource_mgr.tool()
            if hasattr(tool_mgr, 'cleanup') and callable(tool_mgr.cleanup):
                await tool_mgr.cleanup()
            logger.info("[IterativeFlow] MCP resources cleaned up")
        except Exception as e:
            logger.warning(f"[IterativeFlow] Resource cleanup warning: {e}")
    
    def _generate_final_report(self, iterations: int, elapsed: float) -> str:
        """生成最终报告"""
        stats = self._progress_tracker.get_statistics()
        memory_stats = self._memory_manager.get_statistics()
        
        report = f"""
# Implementation Report (Iterative Mode)

## Summary
- **Iterations**: {iterations}
- **Duration**: {elapsed:.1f}s
- **Files Implemented**: {stats['total_files']}

## Completed Files
{self._format_file_list(stats['completed_files'])}

## Statistics
- Unique Files: {stats['unique_files_count']}
- Technical Decisions: {stats['tech_decisions_count']}
- Final Status: {'Stuck in Analysis' if stats['is_stuck'] else 'Normal'}

## Memory Management
- Stored Messages Count: {memory_stats['stored_messages_count']}
- Total Compressions: {memory_stats['total_compressions']}
"""
        return report
    
    def _format_file_list(self, files: List[str]) -> str:
        """格式化文件列表"""
        if not files:
            return "No files implemented"
        return "\n".join([f"- {f}" for f in files])


# ============================================================
# Part 4: Entry Point
# ============================================================

async def main():
    """主函数"""
    # 创建控制器
    controller = IterativeCodeFlow()
    
    # 初始化
    await controller.initialize()
    
    # 执行
    plan_file = os.getenv("TEST_PLAN_FILE", "D:\\project\\jiuwen\\openjiuwen\\test-agentcore_deepcode\\examples\\deepcode_agent\\tests\\deepcode_lab\\initia"
                                            "l_plan.txt")
    target_dir = os.getenv("TEST_TARGET_DIR", "D:\\project\\jiuwen\\openjiuwen\\test-agentcore_deepcode\\examples\\deepcode_agent\\tests\\deepcode_lab\\test_iml\\test_output\\")
    
    if not os.path.exists(plan_file):
        logger.warning(f"Plan file not found: {plan_file}")
        return
    
    result = await controller.execute(plan_file, target_dir)
    
    logger.info("=" * 60)
    logger.info(f"Final Status: {result['status']}")
    if result['status'] == 'success':
        logger.info(f"Files Implemented: {result['statistics']['total_files']}")
        logger.info(f"Duration: {result['duration_seconds']}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())