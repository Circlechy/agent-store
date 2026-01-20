"""
openjiuwen SDK 集成的 Agent 实现

基于 openjiuwen agent-core SDK 的 ReActAgent 封装
"""

import os
import sys
import logging
import asyncio
import random
from typing import List, Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass

# 添加 agent-core 到路径
AGENT_CORE_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'agent-core'
)
if AGENT_CORE_PATH not in sys.path:
    sys.path.insert(0, AGENT_CORE_PATH)

# ============================================================================
# 禁用 SDK 日志和清理代理环境变量
# ============================================================================

def _clean_proxy_env():
    """清理不兼容的代理环境变量
    
    httpx 不支持 socks 代理，需要清除这些环境变量
    """
    proxy_vars = [
        'http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
        'all_proxy', 'ALL_PROXY'
    ]
    
    for var in proxy_vars:
        proxy_value = os.environ.get(var, '')
        # 如果是 socks 代理，清除它
        if proxy_value and ('socks' in proxy_value.lower()):
            os.environ.pop(var, None)


def _suppress_sdk_logs():
    """禁用 openjiuwen SDK 的日志输出到控制台

    如果 IS_SENSITIVE=false，则不禁用日志（用于调试）
    """
    # 如果 IS_SENSITIVE=false，不禁用日志
    if os.environ.get("IS_SENSITIVE", "true").lower() == "false":
        return

    # 1. 重置 LogManager 使其重新加载配置
    try:
        from openjiuwen.core.common.logging.manager import LogManager
        LogManager.reset()
    except ImportError:
        pass

    # 2. 禁用标准 logging 中的 SDK 相关 logger
    sdk_loggers = [
        'openjiuwen',
        'openjiuwen.core',
        'openjiuwen.agent',
        'common',
        'interface',
        'performance',
    ]

    for logger_name in sdk_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)  # 只显示 CRITICAL 级别
        # 移除所有现有 handler
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        # 添加 NullHandler
        logger.addHandler(logging.NullHandler())
        logger.propagate = False


# 在导入 SDK 之前：清理代理和禁用日志
_clean_proxy_env()
_suppress_sdk_logs()


# 从 openjiuwen SDK 导入
from openjiuwen.agent.react_agent import ReActAgent, create_react_agent_config
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.tool.base import Tool

# 本地模块
from .mode_manager import AgentModeManager, AgentMode
from ..tools.openjiuwen_tools import create_tools_for_mode, create_all_tools
from ..skills.manager import SkillManager
from ..skills.models import Skill


@dataclass
class AgentEvent:
    """Agent 事件（用于流式输出）
    
    事件类型:
    - thinking: 开始思考
    - content_chunk: 流式内容块（逐字输出）
    - content: 完整内容（非流式）
    - tool_call: 工具调用开始
    - tool_result: 工具执行完成
    - error: 错误
    - mode_change: 模式切换
    """
    type: str
    data: Any


# ============================================================================
# Provider 映射
# ============================================================================

# SDK 支持的 provider 映射
PROVIDER_MAP = {
    "anthropic": "openai",  # Anthropic 需要通过 OpenAI 兼容代理
    "zhipu": "zhipu",       # 智谱，我们添加了支持
    "openai": "openai",
    "siliconflow": "siliconflow",
    "custom": "openai",     # 自定义默认使用 OpenAI 兼容格式
}


def get_sdk_provider(provider: str) -> str:
    """将用户 provider 映射为 SDK 支持的 provider"""
    return PROVIDER_MAP.get(provider.lower(), "openai")


class JiuwenCodeAgent:
    """Jiuwen Code Agent
    
    基于 openjiuwen SDK 的 AI 编程助手 Agent
    
    特性：
    - 多模式支持（build/plan/review）
    - 模式感知的工具权限
    - ReAct 推理模式
    """
    
    # 默认系统提示词
    DEFAULT_SYSTEM_PROMPT = """你是 jiuwen，一个 AI 编程助手 CLI 工具。

# 最重要的规则：你必须使用工具！

当用户要求你写代码、创建文件、修改文件时，你**必须**调用相应的工具，**绝对不能**直接在回复中输出代码。

正确做法：
- 用户说"写一个天气程序" → 调用 write_file 工具创建文件
- 用户说"读取 main.py" → 调用 read_file 工具
- 用户说"修改代码" → 调用 edit_file 工具

错误做法：
- 在回复中用 ```python 代码块输出代码 ❌
- 只是描述你会做什么而不调用工具 ❌

# 语气和风格
- 简洁、直接、切中要点
- 回复保持简短（不超过4行），除非用户要求详细说明
- 不要添加不必要的前言或后语

# 任务管理（极其重要！）

你必须使用 todo_write 工具来规划和跟踪任务。这是强制性的，不是可选的。

## 什么时候必须使用 todo_write

当任务满足以下任一条件时，你**必须**先调用 todo_write 规划任务：
1. 需要 2 步或以上才能完成
2. 涉及多个文件的修改
3. 用户给出了多个要求（用逗号、顿号或编号分隔）
4. 需要先搜索/阅读代码再修改
5. 任何非简单问答的编程任务

## todo_write 调用方法（重要！使用简化格式）

创建任务 - 使用 tasks 参数传递字符串，用分号分隔多个任务：
{"action": "create", "tasks": "创建登录表单;实现表单验证;添加错误处理"}

更新任务状态：
{"action": "update", "task_id": "任务ID前8位", "status": "completed"}

列出任务：
{"action": "list"}

## 工作流程（必须严格遵守！）

**关键规则：创建任务后必须立即开始执行，不能停下来等待用户！**

**重要：你可以在一次响应中调用多个工具！** 例如：
- 先调用 todo_write 创建任务
- 然后在同一次响应中调用 write_file 开始执行第一个任务

1. **收到任务后**：调用 todo_write 创建任务列表
2. **创建任务后立即执行**：不要等待，直接开始执行第一个任务（状态已是 in_progress）
3. **完成一个任务后**：
   - 调用 todo_write 更新状态为 completed
   - 立即开始执行下一个任务
4. **重复直到所有任务完成**

## 示例

用户说："帮我写一个用户登录功能，包括表单验证和错误处理"

正确做法：
1. 调用 todo_write(action="create", tasks="创建登录表单组件;实现表单验证逻辑;添加错误处理")
2. **立即**调用 write_file 创建登录表单组件（不要停下来！）
3. 完成后调用 todo_write(action="update", task_id="xxx", status="completed")
4. **立即**开始下一个任务...
5. 重复直到所有任务完成

错误做法：
- 直接开始写代码，不规划 ❌
- 调用 todo_write 但不传 tasks 参数 ❌
- 使用复杂的 todos 数组格式 ❌
- **调用 todo_write 后停下来等待用户** ❌ ← 这是最常见的错误！

# 工具使用
- read_file: 读取文件
- write_file: 创建新文件
- edit_file: 修改现有文件
- bash: 执行命令
- grep/glob: 搜索文件
- todo_write: 管理任务（用 tasks 字符串参数，不要用 todos 数组！）

# 代码风格
- 除非被要求，不要添加注释
- 遵循项目现有的代码风格

# 任务完成规则（强制执行！）

**你必须完成所有任务才能结束对话！**

1. 如果你有未完成的 Todo 项（pending 或 in_progress 状态），你**必须**继续调用工具完成它们
2. 不要在任务未完成时给出总结性回复
3. 不要说"我已经完成了..."除非所有 Todo 都是 completed 状态
4. 每次回复前检查是否还有待完成的工作
5. 如果系统提醒你有未完成任务，立即调用工具继续执行

# 绝对禁止的行为（违反将导致任务失败！）

1. **绝对不能**在有未完成任务时停止工作
2. **绝对不能**只输出文字说明而不调用工具
3. **绝对不能**说"我已经完成了"除非所有 Todo 都是 completed 状态
4. **绝对不能**在创建 Todo 后等待用户确认
5. 如果你发现自己想要停止，立即检查 Todo 列表并继续执行

# 自我检查清单（每次回复前必须检查）

在给出任何回复之前，问自己：
1. 我是否有未完成的 Todo 项？如果有，我必须继续调用工具
2. 我是否在输出代码块而不是调用工具？如果是，改为调用工具
3. 我是否在给出总结性回复？如果是，检查任务是否真的全部完成

**违反这些规则是不可接受的！**
"""
    
    def __init__(
        self,
        model_provider: str = "openai",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: str = "gpt-4o",
        mode_manager: Optional[AgentModeManager] = None,
        max_iterations: int = 100,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        project_root: Optional[str] = None
    ):
        """初始化 Agent

        Args:
            model_provider: 模型提供商 (openai, anthropic, zhipu 等)
            api_key: API 密钥
            api_base: API Base URL
            model_name: 模型名称
            mode_manager: 模式管理器
            max_iterations: 最大迭代次数
            system_prompt: 自定义系统提示词
            session_id: 会话 ID（用于 TodoWrite 等工具）
            project_root: 项目根目录（用于加载项目级 skills）
        """
        self.model_provider = model_provider
        self.api_key = api_key or self._get_api_key_from_env(model_provider)
        self.api_base = api_base or self._get_default_api_base(model_provider)
        self.model_name = model_name
        self.max_iterations = max_iterations

        # 获取 SDK 支持的 provider
        self.sdk_provider = get_sdk_provider(model_provider)

        # 模式管理器
        self.mode_manager = mode_manager or AgentModeManager()

        # 会话 ID（用于 TodoWrite 等工具）
        self.session_id = session_id

        # Skill 管理器
        from pathlib import Path
        self.skill_manager = SkillManager(
            project_root=Path(project_root) if project_root else None
        )
        self.skill_manager.load_skills()

        # 系统提示词
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

        # 工具列表（根据模式动态获取）
        self._tools: List[Tool] = []
        self._refresh_tools()

        # SDK Agent 实例（延迟创建）
        self._agent: Optional[ReActAgent] = None
        self._agent_config = None
    
    def _get_api_key_from_env(self, provider: str) -> Optional[str]:
        """从环境变量获取 API Key"""
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
        }
        env_var = env_map.get(provider.lower())
        if env_var:
            return os.getenv(env_var)
        # 尝试通用的
        return (os.getenv("OPENAI_API_KEY") or 
                os.getenv("ANTHROPIC_API_KEY") or
                os.getenv("ZHIPU_API_KEY"))
    
    def _get_default_api_base(self, provider: str) -> str:
        """获取默认 API Base"""
        defaults = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        }
        return defaults.get(provider.lower(), "https://api.openai.com/v1")
    
    def _refresh_tools(self):
        """刷新工具列表（考虑模式和 skill 权限）"""
        # 先根据模式获取工具（传递 LLM 配置给 Task 子代理）
        tools = create_tools_for_mode(
            mode_manager=self.mode_manager,
            session_id=self.session_id,
            model_provider=self.model_provider,
            api_key=self.api_key,
            api_base=self.api_base,
            model_name=self.model_name
        )
        # 再根据 skill 过滤工具
        self._tools = self.skill_manager.filter_tools(tools)
    
    def _build_model_config(self) -> ModelConfig:
        """构建模型配置"""
        model_info = BaseModelInfo(
            api_key=self.api_key,
            api_base=self.api_base,
            model=self.model_name,
            temperature=0.7,
            top_p=0.9,
            timeout=120,
        )
        
        return ModelConfig(
            model_provider=self.sdk_provider,  # 使用 SDK 支持的 provider
            model_info=model_info
        )
    
    def _build_prompt_template(self) -> List[Dict]:
        """构建提示词模板（包含模式和 skill 提示词）"""
        # 获取模式特定的提示词后缀
        mode_suffix = self.mode_manager.get_mode_prompt_suffix()

        # 获取 skill 提示词后缀
        skill_suffix = self.skill_manager.get_prompt_suffix()

        full_prompt = self.system_prompt
        if mode_suffix:
            full_prompt = f"{full_prompt}\n\n{mode_suffix}"
        if skill_suffix:
            full_prompt = f"{full_prompt}\n\n{skill_suffix}"

        return [{"role": "system", "content": full_prompt}]
    
    def _init_agent(self, force_reinit: bool = False):
        """初始化 SDK Agent

        Args:
            force_reinit: 强制重新初始化（用于更新配置）
        """
        if self._agent is not None and not force_reinit:
            return

        # 再次禁用日志（确保在 Agent 创建前生效）
        _suppress_sdk_logs()

        # 构建配置
        self._agent_config = create_react_agent_config(
            agent_id="jiuwen_code",
            agent_version="0.1.0",
            description="Jiuwen Code - AI 编程助手",
            model=self._build_model_config(),
            prompt_template=self._build_prompt_template()
        )

        # 设置最大迭代次数
        self._agent_config.constrain.max_iteration = self.max_iterations

        # 设置上下文窗口限制（增加到 50 条消息以支持更多工具调用）
        # 这可以避免在多轮工具调用后出现 API 错误
        if hasattr(self._agent_config, 'context_window_limit'):
            self._agent_config.context_window_limit = 50

        # 创建 Agent
        self._agent = ReActAgent(self._agent_config)
        
        # 注册工具到 Agent
        self._agent._tools = self._tools
    
    def refresh_tools(self):
        """刷新工具列表（模式切换后调用）"""
        self._refresh_tools()
        if self._agent:
            self._agent._tools = self._tools
    
    def switch_mode(self, mode: AgentMode) -> bool:
        """切换模式

        Args:
            mode: 目标模式

        Returns:
            是否切换成功
        """
        if self.mode_manager.switch_mode(mode):
            self.refresh_tools()
            # 重新初始化 agent 以应用新的提示词
            self._agent = None
            return True
        return False

    def activate_skill(self, skill_name: str) -> bool:
        """激活指定的 skill

        Args:
            skill_name: Skill 名称

        Returns:
            是否成功激活
        """
        skill = self.skill_manager.get_skill(skill_name)
        if skill:
            self.skill_manager.activate_skill(skill)
            self._refresh_tools()
            # 重新初始化 agent 以应用新的提示词
            self._agent = None
            return True
        return False

    def deactivate_skill(self):
        """停用当前 skill"""
        self.skill_manager.deactivate_skill()
        self._refresh_tools()
        # 重新初始化 agent 以应用新的提示词
        self._agent = None

    def get_current_skill(self):
        """获取当前激活的 skill"""
        return self.skill_manager.current_skill

    def list_skills(self):
        """列出所有可用的 skills"""
        return self.skill_manager.list_skills()
    
    async def invoke(self, query: str, conversation_id: str = "default") -> Dict[str, Any]:
        """调用 Agent（带重试机制）

        Args:
            query: 用户查询
            conversation_id: 会话 ID

        Returns:
            执行结果
        """
        self._init_agent()

        inputs = {
            "query": query,
            "conversation_id": conversation_id
        }

        # 重试配置
        max_retries = 5
        base_delay = 1.0  # 基础延迟（秒）
        max_delay = 60.0  # 最大延迟（秒）

        last_exception = None

        for attempt in range(max_retries):
            try:
                result = await self._agent.invoke(inputs)
                return result
            except Exception as e:
                last_exception = e
                error_str = str(e)

                # 检查是否是可重试的错误
                is_retryable = self._is_retryable_error(error_str)

                if is_retryable and attempt < max_retries - 1:
                    # 计算指数退避延迟
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    # 添加随机抖动 (0.5 - 1.5 倍)
                    jitter = 0.5 + random.random()
                    actual_delay = delay * jitter

                    # 记录重试信息
                    print(f"[Agent] API 错误，{actual_delay:.1f}秒后重试 (第{attempt + 1}/{max_retries}次)...")

                    await asyncio.sleep(actual_delay)
                    continue

                # 不可重试的错误或已达最大重试次数
                break

        # 返回错误结果
        return {
            "output": f"Agent 执行错误: {str(last_exception)}",
            "result_type": "error"
        }

    def _is_retryable_error(self, error_str: str) -> bool:
        """判断错误是否可重试

        可重试的错误类型：
        - 连接错误 (connection error, timeout)
        - 速率限制 (429, rate limit)
        - 服务器错误 (500, 502, 503, 504)
        """
        error_lower = error_str.lower()

        retryable_patterns = [
            # 连接错误
            "connection",
            "timeout",
            "timed out",
            "connect",
            "reset by peer",
            "broken pipe",
            "network",
            "socket",
            # 速率限制
            "429",
            "rate limit",
            "too many requests",
            "quota",
            "throttl",
            # 服务器错误
            "500",
            "502",
            "503",
            "504",
            "server error",
            "internal error",
            "service unavailable",
            "bad gateway",
            # OpenAI 特定错误
            "openai api",
            "async conn",
            "failed to call model",
        ]

        return any(pattern in error_lower for pattern in retryable_patterns)
    
    async def stream(
        self,
        query: str,
        conversation_id: str = "default"
    ) -> AsyncIterator[AgentEvent]:
        """流式调用 Agent（带重试机制）

        Args:
            query: 用户查询
            conversation_id: 会话 ID

        Yields:
            AgentEvent: Agent 事件
            - thinking: 开始思考
            - content_chunk: 流式内容块（逐字输出）
            - content: 完整内容
            - tool_call: 工具调用
            - tool_result: 工具结果
            - error: 错误
        """
        self._init_agent()

        inputs = {
            "query": query,
            "conversation_id": conversation_id
        }

        # 重试配置
        max_retries = 5
        base_delay = 1.0
        max_delay = 60.0

        for attempt in range(max_retries):
            has_content = False
            has_content_chunk = False
            has_error = False
            should_retry = False

            try:
                async for chunk in self._agent.stream(inputs):
                    event = self._parse_stream_chunk(chunk)
                    if event:
                        if event.type == "content_chunk" and event.data:
                            has_content_chunk = True
                            has_content = True
                        elif event.type == "content" and event.data:
                            if has_content_chunk:
                                continue
                            has_content = True
                        elif event.type == "error":
                            has_error = True
                            # 检查是否是可重试的错误
                            if self._is_retryable_error(str(event.data)) and attempt < max_retries - 1:
                                should_retry = True
                                break
                        yield event

                if should_retry:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = 0.5 + random.random()
                    actual_delay = delay * jitter
                    print(f"[Agent] API 错误，{actual_delay:.1f}秒后重试 (第{attempt + 1}/{max_retries}次)...")
                    await asyncio.sleep(actual_delay)
                    continue

                if not has_content and not has_error:
                    yield AgentEvent(
                        type="error",
                        data="未收到模型响应，请检查 API 配置和网络连接"
                    )
                return

            except Exception as e:
                error_str = str(e)
                if self._is_retryable_error(error_str) and attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = 0.5 + random.random()
                    actual_delay = delay * jitter
                    print(f"[Agent] API 错误，{actual_delay:.1f}秒后重试 (第{attempt + 1}/{max_retries}次)...")
                    await asyncio.sleep(actual_delay)
                    continue

                error_msg = self._format_error(e)
                yield AgentEvent(type="error", data=error_msg)
                return
    
    def _format_error(self, e_or_msg) -> str:
        """格式化错误信息，提取有用的细节
        
        Args:
            e_or_msg: Exception 对象或错误消息字符串
        """
        if isinstance(e_or_msg, Exception):
            error_str = str(e_or_msg)
            error_type = type(e_or_msg).__name__
            # 尝试提取 SDK 特定的错误信息
            if hasattr(e_or_msg, 'message'):
                error_str = e_or_msg.message
            elif hasattr(e_or_msg, 'args') and e_or_msg.args:
                error_str = str(e_or_msg.args[0])
        else:
            error_str = str(e_or_msg)
            error_type = "Error"
        
        # 常见错误的友好提示
        if "Invalid model provider" in error_str:
            return f"模型提供商配置错误: {error_str}\n请检查 provider 设置"
        elif "timeout" in error_str.lower():
            return f"API 连接超时: {error_str}\n请检查网络连接"
        elif "API" in error_str and "error" in error_str.lower():
            return f"API 调用失败: {error_str}\n请检查 API Key 和网络"
        elif "socks" in error_str.lower() or "proxy" in error_str.lower():
            return f"代理错误: {error_str}\n请使用 HTTP 代理或直连"
        elif "api_key" in error_str.lower() or "authentication" in error_str.lower():
            return f"认证失败: {error_str}\n请检查 API Key"
        else:
            return f"{error_type}: {error_str}"
    
    def _parse_stream_chunk(self, chunk) -> Optional[AgentEvent]:
        """解析流式数据块
        
        SDK 返回的 OutputSchema 结构：
        - type: 事件类型
        - payload: 包含实际数据的字典
        
        支持的事件类型：
        - thinking: 思考中
        - content_chunk: 流式内容块
        - tool_call: 工具调用
        - tool_result: 工具结果
        - answer: 最终答案
        - error: 错误
        """
        try:
            # 处理 OutputSchema 对象
            if hasattr(chunk, 'type') and hasattr(chunk, 'payload'):
                chunk_type = chunk.type
                payload = chunk.payload
                
                if chunk_type == "error":
                    # 错误信息
                    if isinstance(payload, dict):
                        error_msg = payload.get("error", str(payload))
                    else:
                        error_msg = str(payload)
                    return AgentEvent(
                        type="error", 
                        data=self._format_error(error_msg)
                    )
                
                elif chunk_type == "content_chunk":
                    # 流式内容块（逐字输出）
                    if isinstance(payload, dict):
                        content = payload.get("content", "")
                    else:
                        content = str(payload)
                    
                    if content:
                        return AgentEvent(type="content_chunk", data=content)
                
                elif chunk_type == "answer":
                    # 最终答案
                    if isinstance(payload, dict):
                        # 检查是否是错误响应
                        if payload.get("result_type") == "error":
                            error_msg = payload.get("output", "未知错误")
                            return AgentEvent(
                                type="error", 
                                data=self._format_error(error_msg)
                            )
                        
                        output = payload.get("output", {})
                        if isinstance(output, dict):
                            content = output.get("output", "")
                        else:
                            content = str(output)
                    else:
                        content = str(payload)
                    
                    # 如果已经通过 content_chunk 输出过，answer 可能为空
                    # 不需要再输出
                    if content:
                        return AgentEvent(type="content", data=content)
                
                elif chunk_type == "tool_call":
                    # 工具调用开始
                    if isinstance(payload, dict):
                        tool_info = payload.get("tool_call", payload)
                    else:
                        tool_info = payload
                    return AgentEvent(type="tool_call", data=tool_info)
                
                elif chunk_type == "tool_result":
                    # 工具执行结果
                    if isinstance(payload, dict):
                        result_info = payload.get("tool_result", payload)
                    else:
                        result_info = payload
                    
                    # 提取结果内容
                    if isinstance(result_info, dict):
                        result = result_info.get("result", str(result_info))
                    else:
                        result = str(result_info)
                    
                    return AgentEvent(type="tool_result", data=result)
                
                elif chunk_type == "thinking":
                    # 思考过程
                    return AgentEvent(type="thinking", data=payload)
                
                else:
                    # 其他类型，过滤调试信息
                    if isinstance(payload, dict):
                        # 跳过 traceId 等调试信息
                        if 'traceId' in payload or 'invokeId' in payload:
                            return None
                        content = payload.get("content") or payload.get("output")
                        if not content:
                            return None
                    else:
                        content = str(payload)
                    
                    if content and not self._is_debug_output(content):
                        return AgentEvent(type="content", data=content)
            
            # 处理普通字典
            elif isinstance(chunk, dict):
                # 跳过 trace 调试信息
                if 'traceId' in chunk or 'invokeId' in chunk:
                    return None
                
                # 检查是否是错误
                if chunk.get("result_type") == "error":
                    error_msg = chunk.get("output", "未知错误")
                    return AgentEvent(
                        type="error", 
                        data=self._format_error(error_msg)
                    )
                
                output = chunk.get("output", "")
                if output and not self._is_debug_output(str(output)):
                    return AgentEvent(type="content", data=str(output))
            
            # 其他类型
            else:
                content = str(chunk)
                if content and not self._is_debug_output(content):
                    return AgentEvent(type="content", data=content)
                    
        except Exception:
            pass
        
        return None
    
    def _is_debug_output(self, content: str) -> bool:
        """检查是否是调试输出，应该被过滤"""
        debug_markers = [
            "'traceId':",
            "'invokeId':",
            "'parentInvokeId':",
            "'childInvokes':",
            "'invokeType':",
            "datetime.datetime(",
            "'startTime':",
            "'endTime':",
            "'elapsedTime':",
        ]
        return any(marker in content for marker in debug_markers)

    def get_current_mode(self) -> AgentMode:
        """获取当前模式"""
        return self.mode_manager.get_current_mode()
    
    def get_available_tools(self) -> List[str]:
        """获取当前可用的工具列表"""
        return [t.name for t in self._tools]
    
    def get_mode_info(self) -> Dict[str, Any]:
        """获取模式信息"""
        return self.mode_manager.get_mode_info()


# ==================== 工厂函数 ====================

def create_jiuwen_agent(
    provider: str = "openai",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    api_base: Optional[str] = None,
    **kwargs
) -> JiuwenCodeAgent:
    """创建 Jiuwen Code Agent
    
    Args:
        provider: 模型提供商 (openai, anthropic, zhipu)
        api_key: API 密钥（可从环境变量获取）
        model: 模型名称
        api_base: API Base URL
        **kwargs: 其他参数
        
    Returns:
        JiuwenCodeAgent 实例
    """
    # 默认模型
    default_models = {
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-5-20250929",
        "zhipu": "glm-4",
    }
    
    model_name = model or default_models.get(provider.lower(), "gpt-4o")
    
    return JiuwenCodeAgent(
        model_provider=provider,
        api_key=api_key,
        api_base=api_base,
        model_name=model_name,
        **kwargs
    )


def create_agent_from_env() -> JiuwenCodeAgent:
    """从环境变量创建 Agent
    
    支持的环境变量：
    - OPENAI_API_KEY / ANTHROPIC_API_KEY / ZHIPU_API_KEY
    - MODEL_PROVIDER (默认 openai)
    - MODEL_NAME
    - API_BASE_URL
    
    Returns:
        JiuwenCodeAgent 实例
    """
    # 检测可用的 API Key
    if os.getenv("ZHIPU_API_KEY"):
        provider = "zhipu"
        api_key = os.getenv("ZHIPU_API_KEY")
    elif os.getenv("ANTHROPIC_API_KEY"):
        provider = "anthropic"
        api_key = os.getenv("ANTHROPIC_API_KEY")
    elif os.getenv("OPENAI_API_KEY"):
        provider = "openai"
        api_key = os.getenv("OPENAI_API_KEY")
    else:
        # 无 API Key，返回一个占位 Agent（用于测试）
        provider = os.getenv("MODEL_PROVIDER", "openai")
        api_key = None
    
    # 覆盖提供商（如果环境变量指定）
    provider = os.getenv("MODEL_PROVIDER", provider)
    
    # 模型名称
    model = os.getenv("MODEL_NAME")
    
    # API Base
    api_base = os.getenv("API_BASE_URL")
    
    return create_jiuwen_agent(
        provider=provider,
        api_key=api_key,
        model=model,
        api_base=api_base
    )
