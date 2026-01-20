"""
Agent 基类

基于 openJiuwen.BaseAgent 的适配层，提供统一的接口
"""
from typing import Dict, Any, Optional, AsyncIterator, Callable
import asyncio
import time
from loguru import logger

from openjiuwen.core.agent.agent import BaseAgent as OpenJiuwenBaseAgent
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.agent.config.base import AgentConfig
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.common.utlis.hash_util import generate_key

from app.context.context_manager import ContextManager
from app.models.agent_result import AgentResult


# 🔍 [DEBUG] 调试工具函数 - 调试结束后可删除
def _debug_truncate(obj, max_len=1000):
    """截断对象为字符串，用于调试日志"""
    s = str(obj)
    if len(s) > max_len:
        return s[:max_len] + f"...[截断,原长{len(s)}]"
    return s


class VibeBaseAgent(OpenJiuwenBaseAgent):
    """
    Vibe Agent 基类 - 正确继承 openJiuwen.BaseAgent
    
    提供统一的接口和辅助方法，子类只需实现 invoke() 和 stream()
    """
    
    def __init__(
        self,
        agent_config: AgentConfig,
        context_manager: Optional[ContextManager] = None
    ):
        """
        初始化 Agent
        
        Args:
            agent_config: openJiuwen 的 AgentConfig 实例（必须包含 model）
            context_manager: 上下文管理器（可选）
        """
        super().__init__(agent_config)
        self.context_manager = context_manager
        logger.info(f"初始化 Agent: {agent_config.id}")
    
    def _get_model(self, runtime: Runtime = None) -> Any:
        """
        获取模型实例（推荐方式：通过 Runtime）
        
        Args:
            runtime: Runtime 实例（可选，默认使用 self._runtime）
        
        Returns:
            BaseModelClient 实例
        """
        if runtime is None:
            runtime = self._runtime
        
        # 生成模型 ID（用于缓存）
        model_id = generate_key(
            self.agent_config.model.model_info.api_key,
            self.agent_config.model.model_info.api_base,
            self.agent_config.model.model_provider
        )
        
        # 兼容不同的 Runtime 类型
        # 1. 如果 runtime 有 get_model 方法（WrappedRuntime/TaskRuntime），直接使用
        # 2. 否则，通过 resource_manager 获取（AgentRuntime 等）
        if hasattr(runtime, 'get_model'):
            # 使用 Runtime 的 get_model 方法（WrappedRuntime/TaskRuntime）
            model = runtime.get_model(model_id=model_id)
            
            if model is None:
                # 创建新模型并添加到 Runtime
                model_extra = {
                    k: v for k, v in self.agent_config.model.model_info.model_extra.items()
                    if k not in ('model_name', 'model', 'api_key', 'api_base', 'timeout', 'temperature', 'top_p')
                }
                model = ModelFactory().get_model(
                    model_provider=self.agent_config.model.model_provider,
                    api_key=self.agent_config.model.model_info.api_key,
                    api_base=self.agent_config.model.model_info.api_base,
                    timeout=self.agent_config.model.model_info.timeout,
                    temperature=self.agent_config.model.model_info.temperature,
                    top_p=self.agent_config.model.model_info.top_p,
                    **model_extra
                )
                runtime.add_model(model_id=model_id, model=model)
            
            return runtime.get_model(model_id=model_id)
        else:
            # 通过 resource_manager 获取（兼容 AgentRuntime）
            resource_manager = runtime.resource_manager()
            model_mgr = resource_manager.model()
            
            # 尝试获取已缓存的模型
            model = model_mgr.get_model(model_id=model_id, runtime=runtime)
            
            if model is None:
                # 创建新模型并添加到 ModelMgr
                model_extra = {
                    k: v for k, v in self.agent_config.model.model_info.model_extra.items()
                    if k not in ('model_name', 'model', 'api_key', 'api_base', 'timeout', 'temperature', 'top_p')
                }
                model = ModelFactory().get_model(
                    model_provider=self.agent_config.model.model_provider,
                    api_key=self.agent_config.model.model_info.api_key,
                    api_base=self.agent_config.model.model_info.api_base,
                    timeout=self.agent_config.model.model_info.timeout,
                    temperature=self.agent_config.model.model_info.temperature,
                    top_p=self.agent_config.model.model_info.top_p,
                    **model_extra
                )
                model_mgr.add_model(model_id=model_id, model=model)
                # 再次获取（带 trace 装饰）
                model = model_mgr.get_model(model_id=model_id, runtime=runtime)
            
            return model
    
    async def _call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        runtime: Runtime = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        调用 LLM
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            runtime: Runtime 实例（可选）
            temperature: 温度参数（可选）
        
        Returns:
            LLM 响应文本
        """
        model = self._get_model(runtime)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            logger.debug(f"📤 LLM 请求: model={self.agent_config.model.model_info.model_name}, "
                        f"api_base={self.agent_config.model.model_info.api_base}")
            response = await model.ainvoke(
                model_name=self.agent_config.model.model_info.model_name,
                messages=messages,
                temperature=temperature or self.agent_config.model.model_info.temperature,
                top_p=self.agent_config.model.model_info.top_p
            )
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            # 获取原始异常（如果被包装过）
            original_error = e.__cause__ if e.__cause__ else e
            logger.error(f"❌ LLM 调用失败: {e}")
            logger.error(f"   原始异常: {type(original_error).__name__}: {original_error}")
            logger.error(f"   API Base: {self.agent_config.model.model_info.api_base}")
            logger.error(f"   Model: {self.agent_config.model.model_info.model_name}")
            raise
    
    async def _call_llm_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        runtime: Runtime = None,
        temperature: Optional[float] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> AsyncIterator[str]:
        """
        流式调用 LLM
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            runtime: Runtime 实例（可选）
            temperature: 温度参数（可选）
            on_chunk: 接收到每个 chunk 时的回调函数（可选）
        
        Yields:
            LLM 响应文本片段
        """
        model = self._get_model(runtime)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            logger.debug(f"📤 LLM 流式请求: model={self.agent_config.model.model_info.model_name}")
            async for chunk in model.astream(
                model_name=self.agent_config.model.model_info.model_name,
                messages=messages,
                temperature=temperature or self.agent_config.model.model_info.temperature,
                top_p=self.agent_config.model.model_info.top_p
            ):
                content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if content:
                    if on_chunk:
                        on_chunk(content)
                    yield content
        except Exception as e:
            logger.error(f"❌ LLM 流式调用失败: {e}")
            raise
    
    async def _generate_thinking_stream(
        self,
        thinking_prompt: str,
        system_prompt: str,
        event_queue: Optional[asyncio.Queue] = None,
        step_id: Optional[str] = None,
        step_name: Optional[str] = None,
        runtime: Runtime = None
    ) -> str:
        """
        流式生成思考过程
        
        Args:
            thinking_prompt: 思考提示词
            system_prompt: 系统提示词
            event_queue: 事件队列（用于发送实时思考片段）
            step_id: 步骤ID（可选）
            step_name: 步骤名称（可选）
            runtime: Runtime 实例（可选）
        
        Returns:
            完整的思考内容
        """
        accumulated_thought = ""
        
        def on_chunk(content: str):
            """处理每个 chunk 的回调"""
            nonlocal accumulated_thought
            accumulated_thought += content
            
            # 实时发送思考片段到事件队列
            if event_queue:
                try:
                    event_queue.put_nowait({
                        "type": "step_thinking",
                        "step_id": step_id,
                        "step_name": step_name,
                        "message": content,  # 增量内容
                        "data": {"thought": accumulated_thought},  # 完整内容
                        "timestamp": time.time()
                    })
                except asyncio.QueueFull:
                    logger.warning(f"事件队列已满，跳过思考片段发送")
        
        # 流式调用 LLM
        async for chunk in self._call_llm_stream(
            prompt=thinking_prompt,
            system_prompt=system_prompt,
            runtime=runtime,
            on_chunk=on_chunk
        ):
            # chunk 已经在 on_chunk 中处理了
            pass
        
        logger.info(f"✅ 思考过程生成完成，长度: {len(accumulated_thought)} 字符")
        return accumulated_thought
    
    def _result_to_agent_result(self, result: Dict[str, Any]) -> AgentResult:
        """
        将 openJiuwen 的 result 转换为 AgentResult 格式
        
        Args:
            result: openJiuwen 的 result
        
        Returns:
            AgentResult 实例
        """
        success = result.get("success", True)
        data = result.get("data", result)
        error = result.get("error")
        metadata = result.get("metadata", {})
        
        return AgentResult(
            success=success,
            data=data,
            error=error,
            metadata=metadata
        )
