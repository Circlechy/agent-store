"""NovaStar主工作流模块.

基于openjiuwen框架构建的完整Agent工作流。
"""

import ast
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.core.component.branch_router import BranchRouter
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.runner.runner import Runner
from openjiuwen.core.runtime.config import WorkflowConfig
from openjiuwen.core.stream.base import CustomSchema, OutputSchema
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.workflow.workflow_config import WorkflowMetadata

from novastar.core.llm_wrapper import LLMWrapper, create_llm_from_config
from novastar.core.global_context import GlobalContextManager
from novastar.nodes.commander_node import (
    CommanderNode,
    AgentType,
    IntentRouterNode,
    IntentType,
)
from novastar.nodes.mentor_node import MentorNode
from novastar.nodes.artist_node import ArtistNode
from novastar.nodes.companion_node import CompanionNode

logger = logging.getLogger(__name__)


class NodeId:
    """节点ID常量."""
    START = "start"
    END = "end"
    INTENT_ROUTER = "intent_router"
    COMMANDER = "commander"
    MENTOR = "mentor"
    ARTIST = "artist"
    COMPANION = "companion"


def init_router(current_node: str, next_nodes: Union[str, List[str]]) -> BranchRouter:
    """初始化路由器（参考openjiuwen的使用方式）.

    Args:
        current_node: 当前节点ID
        next_nodes: 下一个节点ID或节点ID列表

    Returns:
        BranchRouter实例
    """
    router = BranchRouter()
    if isinstance(next_nodes, str):
        condition = f"${{{current_node}.next_node}} == {next_nodes!r}"
        router.add_branch(condition, next_nodes)
    elif isinstance(next_nodes, list):
        for next_node in next_nodes:
            condition = f"${{{current_node}.next_node}} == {next_node!r}"
            router.add_branch(condition, next_node)
    return router


class NovaStarWorkflow:
    """NovaStar主工作流.

    集成所有Agent节点，构建完整的儿童AI伴学工作流。
    """

    def __init__(
        self,
        workflow_name: str = "novastar_workflow",
        version: str = "1.0",
        llm_config: Optional[Dict[str, Any]] = None,
        agent_config: Optional[Dict[str, Any]] = None,
    ):
        """初始化NovaStar工作流.

        Args:
            workflow_name: 工作流名称
            version: 工作流版本
            llm_config: LLM配置
            agent_config: Agent配置
        """
        self.workflow_name = workflow_name
        self.version = version
        self.llm_config = llm_config or {}
        self.agent_config = agent_config or {}

        self._llm: Optional[LLMWrapper] = None
        self._workflow: Optional[Workflow] = None
        self._agent: Optional[WorkflowAgent] = None
        self._nodes: Dict[str, Any] = {}

        self._initialized = False

    def initialize(self) -> None:
        """初始化工作流（包括LLM和节点）."""
        if self._initialized:
            return

        logger.info("初始化NovaStar工作流: %s", self.workflow_name)

        # 初始化LLM
        self._init_llm()

        # 初始化节点
        self._init_nodes()

        # 构建工作流
        self._build_workflow()

        # 创建Agent
        self._create_agent()

        self._initialized = True
        logger.info("NovaStar工作流初始化完成")

    def _init_llm(self) -> None:
        """初始化LLM."""
        if self.llm_config:
            self._llm = create_llm_from_config(self.llm_config)
            LLMWrapper.register("default", self._llm)
            logger.info("LLM初始化完成")
        else:
            logger.warning("LLM配置为空，将使用模拟响应")

    def _init_nodes(self) -> None:
        """初始化所有节点."""
        node_config = {
            "llm": self.llm_config,
        }

        # 创建节点实例
        self._nodes = {
            NodeId.INTENT_ROUTER: IntentRouterNode(config=node_config),
            NodeId.COMMANDER: CommanderNode(config=node_config),
            NodeId.MENTOR: MentorNode(config=node_config),
            NodeId.ARTIST: ArtistNode(config=node_config),
            NodeId.COMPANION: CompanionNode(config=node_config),
        }

        # 为所有节点设置LLM
        if self._llm:
            for node in self._nodes.values():
                node.set_llm(self._llm)

        logger.info("初始化了%d个节点", len(self._nodes))

    def _build_workflow(self) -> None:
        """构建工作流."""
        # 创建工作流配置
        workflow_config = WorkflowConfig(
            metadata=WorkflowMetadata(
                id=self.workflow_name,
                version=self.version,
                name=self.workflow_name,
            )
        )

        # 创建工作流
        flow = Workflow(workflow_config=workflow_config)

        # 定义输入Schema
        workflow_input_schema = {
            "query": {"type": "string"},
            "user_id": {"type": "string"},
            "conversation_id": {"type": "string"},
            "context": {"type": "object"},
        }

        # Start节点的输入schema：只包含必要的字段
        # user_id 和 conversation_id 应该从运行时上下文获取，不作为输入参数
        startnode_input_schema = {
            "query": "${query}",
            "context": "${context}",
        }

        # Start组件的验证模式：只验证存在的字段
        # 注意：user_id 和 conversation_id 从 runtime 上下文中获取，不在输入中验证
        startnode_valid_mode = [
            {"id": "query", "type": "String", "required": "true", "sourceType": "ref"},
            {"id": "context", "type": "Object", "required": "false", "sourceType": "ref"},
        ]

        # 设置起始节点
        flow.set_start_comp(
            start_comp_id=NodeId.START,
            component=Start({"inputs": startnode_valid_mode}),
            inputs_schema=startnode_input_schema,
        )

        # 添加处理节点
        flow.add_workflow_comp(NodeId.INTENT_ROUTER, self._nodes[NodeId.INTENT_ROUTER])
        flow.add_workflow_comp(NodeId.COMMANDER, self._nodes[NodeId.COMMANDER])
        flow.add_workflow_comp(NodeId.MENTOR, self._nodes[NodeId.MENTOR])
        flow.add_workflow_comp(NodeId.ARTIST, self._nodes[NodeId.ARTIST])
        flow.add_workflow_comp(NodeId.COMPANION, self._nodes[NodeId.COMPANION])

        # 设置结束节点
        flow.set_end_comp(NodeId.END, End())

        # 添加连接
        # START -> INTENT_ROUTER
        flow.add_connection(NodeId.START, NodeId.INTENT_ROUTER)

        # INTENT_ROUTER -> COMMANDER/MENTOR/ARTIST/COMPANION (根据意图路由)
        intent_router = init_router(
            NodeId.INTENT_ROUTER,
            [NodeId.COMMANDER, NodeId.MENTOR, NodeId.ARTIST, NodeId.COMPANION, NodeId.END]
        )
        flow.add_conditional_connection(NodeId.INTENT_ROUTER, router=intent_router)

        # COMMANDER/MENTOR/ARTIST/COMPANION -> END
        flow.add_connection(NodeId.COMMANDER, NodeId.END)
        flow.add_connection(NodeId.MENTOR, NodeId.END)
        flow.add_connection(NodeId.ARTIST, NodeId.END)
        flow.add_connection(NodeId.COMPANION, NodeId.END)

        self._workflow = flow
        logger.info("工作流构建完成")

    def _create_agent(self) -> None:
        """创建WorkflowAgent."""
        if self._workflow is None:
            raise RuntimeError("工作流未构建，请先调用_build_workflow")

        # 定义输入Schema
        workflow_input_schema = {
            "query": {"type": "string"},
            "user_id": {"type": "string"},
            "conversation_id": {"type": "string"},
            "context": {"type": "object"},
        }

        # 创建工作流Schema
        workflow_schema = WorkflowSchema(
            id=self.workflow_name,
            version=self.version,
            name=self.workflow_name,
            description="NovaStar儿童AI伴学工作流",
            inputs=workflow_input_schema,
        )

        # 创建Agent配置
        workflow_config = WorkflowAgentConfig(
            workflows=[workflow_schema]
        )

        # 创建Agent
        self._agent = WorkflowAgent(workflow_config)
        self._agent.add_workflows([self._workflow])

        logger.info("WorkflowAgent创建完成")

    async def run(
        self,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        intent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """运行工作流.

        Args:
            query: 用户查询
            user_id: 用户ID
            conversation_id: 会话ID
            context: 上下文

        Yields:
            工作流输出
        """
        if not self._initialized:
            self.initialize()

        # 确保必需字段不为 None
        if user_id is None:
            user_id = "default_user"
        
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        user_context = context or {}
        GlobalContextManager.update(user_context)
        merged_context = {
            **GlobalContextManager.snapshot(),
            **user_context,
        }

        inputs = {
            "query": query,
            "user_id": str(user_id),  # 确保是字符串
            "conversation_id": str(conversation_id),  # 确保是字符串
            "context": merged_context,
        }
        if intent:
            inputs["intent"] = intent

        logger.info("开始运行工作流: user_id=%s, query=%s...", user_id, query[:50])

        try:
            intent_value = None
            if intent:
                normalized_intent = str(intent).strip().lower()
                for intent_item in IntentType:
                    if intent_item.value == normalized_intent:
                        intent_value = intent_item
                        break
            if intent_value is None:
                intent_router = self._nodes.get(NodeId.INTENT_ROUTER)
                if intent_router:
                    try:
                        intent_value = await intent_router._identify_intent(query)
                    except Exception:
                        intent_value = IntentType.UNKNOWN
            if intent_value is None:
                intent_value = IntentType.UNKNOWN

            intent_router = self._nodes.get(NodeId.INTENT_ROUTER)
            target_agent = None
            if intent_router:
                target_agent, _ = intent_router._route_task(intent_value)

            node_map = {
                AgentType.MENTOR: NodeId.MENTOR,
                AgentType.ARTIST: NodeId.ARTIST,
                AgentType.COMPANION: NodeId.COMPANION,
                AgentType.COMMANDER: NodeId.COMMANDER,
            }
            stream_node_id = node_map.get(target_agent, NodeId.COMPANION)
            stream_node = self._nodes.get(stream_node_id)
            if stream_node and hasattr(stream_node, "stream_response"):
                async for chunk in stream_node.stream_response(
                    query=query,
                    user_id=str(user_id),
                    user_context=merged_context,
                    intent=intent_value.value,
                ):
                    yield self._build_output_message(conversation_id, chunk)
                return

            async for chunk in Runner.run_agent_streaming(
                agent=self._agent,
                inputs=inputs,
            ):
                yield self._build_output_message(conversation_id, chunk)
        except Exception as e:
            logger.error("工作流运行失败: %s", e)
            yield {
                "conversation_id": conversation_id,
                "error": str(e),
                "response": "抱歉，我遇到了一些问题。请稍后再试。",
            }

    def _build_output_message(
        self, conversation_id: str, chunk: Any
    ) -> Dict[str, Any]:
        """构建输出消息.

        Args:
            conversation_id: 会话ID
            chunk: 输出片段

        Returns:
            格式化的输出消息
        """
        if isinstance(chunk, CustomSchema):
            return {
                "conversation_id": conversation_id,
                "agent": getattr(chunk, "agent", "unknown"),
                "content": getattr(chunk, "content", ""),
                "message_type": getattr(chunk, "message_type", ""),
                "event": getattr(chunk, "event", ""),
            }
        elif isinstance(chunk, OutputSchema):
            return {
                "conversation_id": conversation_id,
                "type": "output",
                "payload": getattr(chunk, "payload", None),
            }
        elif isinstance(chunk, dict):
            content_value = chunk.get("content")
            if isinstance(content_value, str) and content_value.startswith("type='tracer_"):
                outputs = self._extract_outputs_from_tracer(content_value)
                if isinstance(outputs, dict) and outputs:
                    return {
                        "conversation_id": conversation_id,
                        **outputs,
                    }
            return {
                "conversation_id": conversation_id,
                **chunk,
            }
        else:
            return {
                "conversation_id": conversation_id,
                "content": str(chunk),
            }

    async def process_message(
        self,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        intent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """处理单条消息（非流式）.

        Args:
            query: 用户查询
            user_id: 用户ID
            conversation_id: 会话ID
            context: 上下文

        Returns:
            最终响应结果
        """
        user_context = context or {}
        GlobalContextManager.update(user_context)
        merged_context = {
            **GlobalContextManager.snapshot(),
            **user_context,
        }

        final_result = {
            "query": query,
            "user_id": user_id,
            "conversation_id": conversation_id or str(uuid.uuid4()),
            "response": "",
            "intent": "",
            "handled_by": "",
        }

        try:
            direct_result = await self._process_direct(query, user_id, intent, merged_context)
            self._merge_result(final_result, direct_result)
            return final_result
        except Exception:
            async for chunk in self.run(query, user_id, conversation_id, intent, merged_context):
                self._merge_result(final_result, chunk)

            self._drop_tracer_content(final_result)
            return final_result

    def _merge_result(self, final_result: Dict[str, Any], chunk: Any) -> None:
        """合并输出结果."""
        data = None
        if isinstance(chunk, dict):
            data = chunk
        elif hasattr(chunk, "outputs"):
            data = getattr(chunk, "outputs")

        if isinstance(data, dict) and "outputs" in data and isinstance(data["outputs"], dict):
            data = data["outputs"]

        if isinstance(data, dict):
            if data.get("response"):
                final_result["response"] = data["response"]
            if data.get("intent"):
                final_result["intent"] = data["intent"]
            if data.get("handled_by"):
                final_result["handled_by"] = data["handled_by"]
            if data.get("content_type"):
                final_result["content_type"] = data["content_type"]
            if data.get("content"):
                content_value = data["content"]
                if not (
                    isinstance(content_value, str)
                    and content_value.startswith("type='tracer_")
                ):
                    final_result["content"] = content_value
            if data.get("metadata"):
                final_result["metadata"] = data["metadata"]

    @staticmethod
    def _drop_tracer_content(final_result: Dict[str, Any]) -> None:
        """移除tracer内容，避免前端显示."""
        content_value = final_result.get("content")
        if isinstance(content_value, str) and content_value.lstrip().startswith("type='tracer_"):
            final_result.pop("content", None)

    @staticmethod
    def _is_tracer_content(content_value: Any) -> bool:
        if isinstance(content_value, str):
            return content_value.lstrip().startswith("type='tracer_")
        return False

    @staticmethod
    def _extract_outputs_from_tracer(content: str) -> Optional[Dict[str, Any]]:
        """从tracer字符串中提取outputs字段."""
        marker = "outputs': "
        start_idx = content.find(marker)
        if start_idx == -1:
            return None

        start_idx += len(marker)
        if start_idx >= len(content) or content[start_idx] != "{":
            return None

        depth = 0
        end_idx = None
        for i in range(start_idx, len(content)):
            char = content[i]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break

        if end_idx is None:
            return None

        outputs_str = content[start_idx : end_idx + 1]
        try:
            outputs = ast.literal_eval(outputs_str)
        except (SyntaxError, ValueError):
            return None

        return outputs if isinstance(outputs, dict) else None

    async def _process_direct(
        self,
        query: str,
        user_id: str,
        intent: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """当工作流未产出有效结果时，直接调用节点生成回复."""
        if not self._initialized:
            self.initialize()

        intent_value = None
        if intent:
            intent_value = intent.strip().lower()

        if intent_value:
            matched_intent = None
            for candidate in IntentType:
                if candidate.value == intent_value:
                    matched_intent = candidate
                    break
            intent_type = matched_intent or IntentType.CHAT
        else:
            intent_type = await self._nodes[NodeId.INTENT_ROUTER]._identify_intent(query)

        user_context = context or {}
        GlobalContextManager.update(user_context)
        merged_context = {
            **GlobalContextManager.snapshot(),
            **user_context,
        }

        # 如果是问答意图，直接调用 mentor 的 answer_question 方法
        if intent_type == IntentType.QA:
            mentor_node = self._nodes[NodeId.MENTOR]
            age = merged_context.get("age", 6)
            answer_result = await mentor_node.answer_question(query, age)
            
            # 格式化返回结果
            result = {
                "query": query,
                "user_id": str(user_id),
                "response": answer_result.get("answer_content", ""),
                "content": {
                    "question": answer_result.get("question", query),
                    "answer_content": answer_result.get("answer_content", ""),
                    "image": answer_result.get("image", ""),
                    "audio": answer_result.get("audio", ""),
                },
                "content_type": "qa",
                "lesson_type": "qa",
                "intent": intent_type.value,
                "handled_by": "mentor",
            }
            return result
        
        # 其他意图使用原来的逻辑
        if intent_type == IntentType.LEARNING:
            node = self._nodes[NodeId.MENTOR]
        elif intent_type == IntentType.STORY:
            node = self._nodes[NodeId.ARTIST]
        else:
            node = self._nodes[NodeId.COMPANION]

        inputs = {
            "query": query,
            "user_id": str(user_id),
            "context": merged_context,
        }

        result = await node._do_invoke(inputs, runtime=None, context=None)
        if isinstance(result, dict):
            result.setdefault("intent", intent_type.value)
        return result if isinstance(result, dict) else {"response": str(result)}


def create_novastar_workflow(
    llm_config: Optional[Dict[str, Any]] = None,
    agent_config: Optional[Dict[str, Any]] = None,
) -> NovaStarWorkflow:
    """创建NovaStar工作流的便捷函数.

    Args:
        llm_config: LLM配置，包含:
            - model_type: 模型类型 (openai, siliconflow等)
            - model_name: 模型名称
            - api_key: API密钥
            - api_base: API基础URL (可选)
        agent_config: Agent配置（预留扩展）

    Returns:
        NovaStarWorkflow实例
    """
    workflow = NovaStarWorkflow(
        workflow_name="novastar_main",
        version="1.0",
        llm_config=llm_config,
        agent_config=agent_config,
    )
    workflow.initialize()
    return workflow
