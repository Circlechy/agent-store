"""基于openjiuwen的节点基类模块.

提供NovaStar Agent节点的基类，继承openjiuwen的WorkflowComponent。
"""

import logging
from abc import abstractmethod
from typing import Any, Dict, Optional

from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.runtime.base import ComponentExecutable
from openjiuwen.core.runtime.runtime import Runtime

from novastar.core.llm_wrapper import LLMWrapper
from novastar.core.global_context import GlobalContextManager

logger = logging.getLogger(__name__)


class NovaStarBaseNode(ComponentExecutable, WorkflowComponent):
    """NovaStar节点基类.

    继承自openjiuwen的ComponentExecutable和WorkflowComponent，
    所有NovaStar的Agent节点都应该继承此类。

    子类需要实现:
    - _pre_handle: 从Runtime上下文中获取必要字段
    - _do_invoke: 核心节点逻辑
    - _post_handle: 把必要字段更新到Runtime上下文中
    """

    def __init__(self, name: str = "BaseNode", config: Optional[Dict[str, Any]] = None):
        """初始化节点.

        Args:
            name: 节点名称
            config: 节点配置
        """
        super().__init__()
        self.name = name
        self.config = config or {}
        self._llm: Optional[LLMWrapper] = None

    def set_llm(self, llm: LLMWrapper) -> None:
        """设置LLM实例.

        Args:
            llm: LLM实例
        """
        self._llm = llm

    def get_llm(self) -> Optional[LLMWrapper]:
        """获取LLM实例.

        Returns:
            LLM实例，如果未设置则尝试从全局获取
        """
        if self._llm is not None:
            return self._llm
        # 尝试从全局获取
        return LLMWrapper.get()

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """节点调用入口.

        此方法不需要子类覆写，用于统一注入横切逻辑（如计时、日志、异常处理等）。

        Args:
            inputs: 输入数据
            runtime: 运行时环境
            context: 上下文

        Returns:
            输出数据
        """
        logger.debug("[%s] 开始执行节点", self.name)
        try:
            # 预处理：从上下文获取必要字段
            self._pre_handle(inputs, runtime, context)

            # 执行核心逻辑
            result = await self._do_invoke(inputs, runtime, context)

            # 后处理：更新上下文
            self._post_handle(inputs, result, runtime, context)

            logger.debug("[%s] 节点执行完成", self.name)
            return result
        except Exception as e:
            logger.error("[%s] 节点执行失败: %s", self.name, e)
            raise

    def _pre_handle(
        self,
        inputs: Input,  # noqa: ARG002
        runtime: Runtime,  # noqa: ARG002
        context: Context,  # noqa: ARG002
    ) -> Dict[str, Any]:
        """预处理：从Runtime上下文中获取必要字段.

        子类可以覆写此方法以获取特定字段。

        Args:
            inputs: 输入数据
            runtime: 运行时环境
            context: 上下文

        Returns:
            预处理结果
        """
        # 同步输入上下文到全局共享上下文
        input_context = self.get_input_value(inputs, "context", {})
        if isinstance(input_context, dict):
            GlobalContextManager.update(input_context)

        for key in ["user_id", "conversation_id", "query"]:
            value = self.get_input_value(inputs, key)
            if value is not None:
                GlobalContextManager.set(key, value)

        return {}

    @abstractmethod
    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """核心节点逻辑.

        子类必须实现此方法。

        Args:
            inputs: 输入数据
            runtime: 运行时环境
            context: 上下文

        Returns:
            输出数据
        """
        raise NotImplementedError("子类必须实现_do_invoke方法")

    def _post_handle(
        self,
        inputs: Input,  # noqa: ARG002
        algorithm_output: Any,  # noqa: ARG002
        runtime: Runtime,  # noqa: ARG002
        context: Context,  # noqa: ARG002
    ) -> None:
        """后处理：把必要字段更新到Runtime上下文中.

        子类可以覆写此方法以更新特定字段。

        Args:
            inputs: 输入数据
            algorithm_output: 算法输出
            runtime: 运行时环境
            context: 上下文
        """
        # 子类可覆写此方法

    async def chat(self, message: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """与LLM对话的便捷方法.

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            **kwargs: 其他参数

        Returns:
            LLM响应
        """
        llm = self.get_llm()
        if llm is None:
            logger.warning("[%s] LLM未配置，返回模拟响应", self.name)
            return f"[模拟响应] {message}"
        return await llm.chat(message, system_prompt=system_prompt, **kwargs)

    async def stream_chat(
        self, message: str, system_prompt: Optional[str] = None, **kwargs
    ):
        """与LLM流式对话的便捷方法.

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            **kwargs: 其他参数

        Yields:
            LLM响应文本片段
        """
        llm = self.get_llm()
        if llm is None:
            logger.warning("[%s] LLM未配置，返回模拟响应", self.name)
            yield f"[模拟响应] {message}"
            return
        async for chunk in llm.stream_chat(message, system_prompt=system_prompt, **kwargs):
            yield chunk

    def get_input_value(self, inputs: Input, key: str, default: Any = None) -> Any:
        """从输入中获取值.

        Args:
            inputs: 输入数据
            key: 键名
            default: 默认值

        Returns:
            输入值
        """
        if hasattr(inputs, key):
            return getattr(inputs, key)
        elif hasattr(inputs, "get"):
            return inputs.get(key, default)
        elif isinstance(inputs, dict):
            return inputs.get(key, default)
        return default

    def set_output_value(self, output: Output, key: str, value: Any) -> None:
        """设置输出值.

        Args:
            output: 输出数据
            key: 键名
            value: 值
        """
        if hasattr(output, key):
            setattr(output, key, value)
        elif hasattr(output, "__setitem__"):
            output[key] = value


class NovaStarStartNode(NovaStarBaseNode):
    """NovaStar起始节点."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化起始节点.

        Args:
            config: 节点配置
        """
        super().__init__(name="StartNode", config=config)

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """起始节点逻辑：将输入传递给后续节点.

        Args:
            inputs: 输入数据
            runtime: 运行时环境
            context: 上下文

        Returns:
            输出数据（直接传递输入）
        """
        logger.info("[StartNode] 工作流开始")
        # 将输入存储到上下文中
        if hasattr(context, "set"):
            for key in ["query", "user_id", "conversation_id", "agent_config"]:
                value = self.get_input_value(inputs, key)
                if value is not None:
                    context.set(key, value)
        return inputs


class NovaStarEndNode(NovaStarBaseNode):
    """NovaStar结束节点."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化结束节点.

        Args:
            config: 节点配置
        """
        super().__init__(name="EndNode", config=config)

    async def _do_invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        """结束节点逻辑：汇总结果.

        Args:
            inputs: 输入数据
            runtime: 运行时环境
            context: 上下文

        Returns:
            最终输出
        """
        logger.info("[EndNode] 工作流结束")
        return inputs
