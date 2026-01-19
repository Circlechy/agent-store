import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# 设置测试环境变量
os.environ.setdefault('MODEL_PROVIDER', 'test')
os.environ.setdefault('MODEL_NAME', 'test-model')
os.environ.setdefault('API_BASE', 'https://test.api')
os.environ.setdefault('API_KEY', 'test-key')

# conftest.py 已经全局 patch 了 logging.basicConfig 和 dotenv.load_dotenv
# 所以可以直接导入
from my_workflow import StartNode, EndNode, build_workflow

from openjiuwen.core.runtime.workflow import WorkflowRuntime


class TestStartNode:
    """测试 StartNode 节点"""

    @pytest.mark.asyncio
    async def test_start_node_invoke(self):
        """测试 StartNode 的 invoke 方法"""
        start_node = StartNode()
        
        # 创建 mock 对象
        mock_runtime = Mock(spec=WorkflowRuntime)
        mock_runtime.update_global_state = Mock()
        
        # 使用空字典作为输入
        mock_inputs = {}
        mock_context = Mock()
        
        # 调用 invoke 方法
        result = await start_node.invoke(mock_inputs, mock_runtime, mock_context)
        
        # 验证 update_global_state 被调用了两次
        assert mock_runtime.update_global_state.call_count == 2
        
        # 验证第一次调用设置了 language
        first_call = mock_runtime.update_global_state.call_args_list[0]
        assert first_call[0][0] == {"language": "Chinese"}
        
        # 验证第二次调用设置了 query
        second_call = mock_runtime.update_global_state.call_args_list[1]
        assert "query" in second_call[0][0]
        assert isinstance(second_call[0][0]["query"], str)
        assert len(second_call[0][0]["query"]) > 0
        
        # 验证返回值
        assert result == mock_inputs


class TestEndNode:
    """测试 EndNode 节点"""

    @pytest.mark.asyncio
    async def test_end_node_invoke(self):
        """测试 EndNode 的 invoke 方法"""
        end_node = EndNode()
        
        # 创建 mock 对象
        mock_runtime = Mock(spec=WorkflowRuntime)
        mock_runtime.get_global_state = Mock(return_value="Test Result")
        
        # 使用空字典作为输入
        mock_inputs = {}
        mock_context = Mock()
        
        # 调用 invoke 方法
        result = await end_node.invoke(mock_inputs, mock_runtime, mock_context)
        
        # 验证 get_global_state 被调用一次
        assert mock_runtime.get_global_state.call_count == 1
        
        # 验证调用的参数是 'result'
        mock_runtime.get_global_state.assert_called_once_with('result')
        
        # 验证返回值
        assert result == mock_inputs


class TestBuildWorkflow:
    """测试 build_workflow 函数"""

    def test_build_workflow_creates_workflow(self):
        """测试 build_workflow 函数是否正确创建工作流"""
        workflow = build_workflow()
        
        # 验证工作流不为 None
        assert workflow is not None
        
        # 验证工作流配置（使用 _workflow_config 私有属性）
        assert workflow._workflow_config is not None
        assert workflow._workflow_config.metadata.name == "Test Workflow"
        assert "Start, TestNode, and End" in workflow._workflow_config.metadata.description

    def test_build_workflow_components(self):
        """测试工作流组件是否正确设置"""
        workflow = build_workflow()
        
        # 验证组件配置存在（使用 _workflow_spec.comp_configs）
        assert "start" in workflow._workflow_spec.comp_configs
        assert "invoke_node" in workflow._workflow_spec.comp_configs
        assert "end" in workflow._workflow_spec.comp_configs
        
        # 验证节点存在于图中
        nodes = workflow._graph.get_nodes()
        assert "start" in nodes
        assert "invoke_node" in nodes
        assert "end" in nodes

    def test_build_workflow_connections(self):
        """测试工作流连接是否正确设置"""
        workflow = build_workflow()
        
        # 验证连接存在（使用 _workflow_spec.edges）
        assert workflow._workflow_spec.edges is not None
        # 连接应该包含 start -> invoke_node 和 invoke_node -> end
        edges = workflow._workflow_spec.edges
        assert "start" in edges
        assert "invoke_node" in edges
        assert "invoke_node" in edges["start"]
        assert "end" in edges["invoke_node"]


class TestWorkflowExecution:
    """测试工作流执行"""

    @pytest.mark.asyncio
    async def test_workflow_execution_with_mocked_test_node(self):
        """测试工作流执行（使用 mock TestNode）"""
        # conftest.py 已经全局 patch 了 logging 和 dotenv，可以直接导入
        from nodes.agent_node import AgentNode
        
        workflow = build_workflow()
        runtime = WorkflowRuntime()
        
        # Mock TestNode 的 _do_invoke 方法
        original_do_invoke = AgentNode._do_invoke
        
        async def mock_do_invoke(self, inputs, runtime, context):
            # 模拟 TestNode 的行为
            runtime.update_global_state({"result": "Mocked Test Result"})
            runtime.update_global_state({"messages": []})
            return inputs
        
        # 应用 mock
        AgentNode._do_invoke = mock_do_invoke
        
        try:
            # 执行工作流
            result = await workflow.invoke(inputs={}, runtime=runtime, context=None)
            
            # 验证全局状态（使用 state().get_global()）
            assert runtime.state().get_global("language") == "Chinese"
            query = runtime.state().get_global("query")
            assert query is not None
            assert isinstance(query, str)
            assert len(query) > 0
            assert runtime.state().get_global("result") == "Mocked Test Result"
            
            # 验证结果不为 None
            assert result is not None
        finally:
            # 恢复原始方法
            AgentNode._do_invoke = original_do_invoke

    @pytest.mark.asyncio
    async def test_workflow_start_and_end_nodes_execution(self):
        """测试 StartNode 和 EndNode 的执行顺序"""
        execution_order = []
        
        # conftest.py 已经全局 patch 了 logging 和 dotenv，可以直接导入
        from nodes.agent_node import AgentNode
        
        # 创建自定义的 StartNode 和 EndNode 来跟踪执行顺序
        class TrackedStartNode(StartNode):
            async def invoke(self, inputs, runtime, context):
                execution_order.append("start")
                runtime.update_global_state({"language": "Chinese"})
                runtime.update_global_state({"query": "Test query"})
                return inputs
        
        class TrackedEndNode(EndNode):
            async def invoke(self, inputs, runtime, context):
                execution_order.append("end")
                return inputs
        
        # 创建工作流
        from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
        from openjiuwen.core.workflow.base import Workflow
        
        config = WorkflowConfig(
            metadata=WorkflowMetadata(
                name="Test Workflow",
                description="Test"
            ),
            inputs_schema=WorkflowInputsSchema(properties={}, required=[])
        )
        
        workflow = Workflow(workflow_config=config)
        workflow.set_start_comp("start", TrackedStartNode())
        workflow.add_workflow_comp("invoke_node", AgentNode())
        workflow.set_end_comp("end", TrackedEndNode())
        workflow.add_connection("start", "invoke_node")
        workflow.add_connection("invoke_node", "end")
        
        runtime = WorkflowRuntime()
        
        # Mock TestNode
        original_do_invoke = AgentNode._do_invoke
        
        async def mock_do_invoke(self, inputs, runtime, context):
            execution_order.append("test_node")
            runtime.update_global_state({"result": "Result"})
            runtime.update_global_state({"messages": []})
            return inputs
        
        AgentNode._do_invoke = mock_do_invoke
        
        try:
            # 执行工作流
            await workflow.invoke(inputs={}, runtime=runtime, context=None)
            
            # 验证执行顺序
            assert execution_order == ["start", "test_node", "end"]
        finally:
            AgentNode._do_invoke = original_do_invoke


class TestWorkflowStateManagement:
    """测试工作流状态管理"""

    @pytest.mark.asyncio
    async def test_global_state_updates(self):
        """测试全局状态更新"""
        workflow = build_workflow()
        runtime = WorkflowRuntime()
        
        # conftest.py 已经全局 patch 了 logging 和 dotenv，可以直接导入
        from nodes.agent_node import AgentNode
        
        original_do_invoke = AgentNode._do_invoke
        
        async def mock_do_invoke(self, inputs, runtime, context):
            runtime.update_global_state({"result": "Test Result"})
            runtime.update_global_state({"messages": []})
            return inputs
        
        AgentNode._do_invoke = mock_do_invoke
        
        try:
            # 执行工作流
            await workflow.invoke(inputs={}, runtime=runtime, context=None)
            
            # 验证全局状态（使用 state().get_global()）
            assert runtime.state().get_global("language") == "Chinese"
            assert runtime.state().get_global("query") is not None
            assert runtime.state().get_global("result") == "Test Result"
            assert runtime.state().get_global("messages") == []
        finally:
            AgentNode._do_invoke = original_do_invoke
