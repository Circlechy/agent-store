"""
智能通勤Agent端到端测试

测试场景：
1. 多途经点通勤（送小孩上学 → 买咖啡 → 公司）
2. 天气查询与空调调整
3. 简单导航查询
4. 不同时间的规划

这是真正的Agent测试，用户只需自然语言输入，Agent自己决定调用什么工具。
"""
import os
import pytest
import dotenv
import asyncio
import logging
import datetime

dotenv.load_dotenv(dotenv_path=".env")

def _ensure_test_env():
    required_keys = [
        "MODEL_PROVIDER",
        "API_BASE",
        "API_KEY",
        "MODEL_NAME",
    ]
    missing = [key for key in required_keys if not os.getenv(key)]
    if missing:
        missing_list = ", ".join(missing)
        pytest.skip(f"缺少必要环境变量: {missing_list}")

_ensure_test_env()

from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.runtime.workflow import WorkflowRuntime

from nodes.smart_commute_agent import SmartCommuteAgent

logger = logging.getLogger(__name__)


class StartNode(Start):
    """测试启动节点"""
    def __init__(self, query: str):
        super().__init__()
        self.query = query
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime.update_global_state({"language": "Chinese"})
        runtime.update_global_state({"query": self.query})
        runtime.update_global_state({"messages": []})
        return inputs


class EndNode(End):
    """测试结束节点"""
    def __init__(self, result_holder: dict):
        super().__init__()
        self.result_holder = result_holder
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        self.result_holder['result'] = runtime.get_global_state("result")
        return inputs


async def run_smart_agent(query: str) -> str:
    """运行智能Agent并返回结果"""
    result_holder = {}
    
    config = WorkflowConfig(
        metadata=WorkflowMetadata(
            name="Smart Agent Test",
            description="Test smart commute agent"
        ),
        inputs_schema=WorkflowInputsSchema(properties={}, required=[])
    )
    
    workflow = Workflow(workflow_config=config)
    workflow.set_start_comp("start", StartNode(query))
    workflow.add_workflow_comp("agent", SmartCommuteAgent())
    workflow.set_end_comp("end", EndNode(result_holder))
    
    workflow.add_connection("start", "agent")
    workflow.add_connection("agent", "end")
    
    runtime = WorkflowRuntime()
    await workflow.invoke(inputs={}, runtime=runtime, context=None)
    
    return result_holder.get('result', '')


class TestSmartAgentE2E:
    """智能通勤Agent端到端测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """设置测试环境"""
        _ensure_test_env()

    @pytest.mark.asyncio
    async def test_multi_stop_commute_natural_language(self):
        """
        测试：用自然语言描述多途经点通勤需求
        
        用户说："导航去公司，我希望九点之前到，要先去送一下小孩上学，然后顺道去买杯瑞幸"
        Agent应该：
        1. 理解需要规划多途经点路线
        2. 自动获取家、学校、瑞幸、公司的坐标
        3. 规划路线并计算预计到达时间
        4. 判断是否能在九点前到达
        """
        query = "导航去公司，我希望九点之前到，要先去送一下小孩上学，然后顺道去买杯瑞幸"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"测试: 多途经点通勤 - 自然语言输入")
        logger.info(f"用户: {query}")
        logger.info(f"{'='*60}")
        
        result = await run_smart_agent(query)
        
        logger.info(f"Agent回复: {result}")
        
        # 验证结果包含关键信息
        assert result is not None
        assert len(result) > 0
        # Agent应该提到路线规划相关信息
        assert any(keyword in result for keyword in ["路线", "导航", "公里", "分钟", "到达", "出发"])
        # Agent应该提到途经点
        assert any(keyword in result for keyword in ["学校", "幼儿园", "瑞幸", "咖啡", "公司"])

    @pytest.mark.asyncio
    async def test_weather_and_ac_adjustment(self):
        """
        测试：查询天气并根据天气调整空调
        
        用户说："今天杭州天气怎么样？帮我调整一下车内空调"
        Agent应该：
        1. 查询杭州天气
        2. 根据气温智能调整空调设置
        3. 返回天气信息和空调调整结果
        """
        query = "今天杭州天气怎么样？帮我调整一下车内空调"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"测试: 天气查询与空调调整")
        logger.info(f"用户: {query}")
        logger.info(f"{'='*60}")
        
        result = await run_smart_agent(query)
        
        logger.info(f"Agent回复: {result}")
        
        # 验证结果包含天气信息
        assert result is not None
        assert any(keyword in result for keyword in ["天气", "气温", "°C", "温度"])
        # 验证结果包含空调调整信息
        assert any(keyword in result for keyword in ["空调", "制热", "制冷", "温度", "模式"])

    @pytest.mark.asyncio
    async def test_simple_navigation(self):
        """
        测试：简单导航查询
        
        用户说："从家到公司怎么走最快？现在出发的话什么时候能到？"
        Agent应该：
        1. 规划从家到公司的最快路线
        2. 根据当前时间计算预计到达时间
        """
        query = "从家到公司怎么走最快？现在出发的话什么时候能到？"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"测试: 简单导航查询")
        logger.info(f"用户: {query}")
        logger.info(f"{'='*60}")
        
        result = await run_smart_agent(query)
        
        logger.info(f"Agent回复: {result}")
        
        # 验证结果包含路线信息
        assert result is not None
        assert any(keyword in result for keyword in ["公里", "分钟", "路线", "导航"])
        # 验证结果包含时间信息
        assert any(keyword in result for keyword in ["到达", "时间", "出发", ":"])

    @pytest.mark.asyncio
    async def test_nearby_search(self):
        """
        测试：搜索附近地点
        
        用户说："公司附近有什么好吃的餐厅推荐吗？"
        Agent应该：
        1. 获取公司坐标
        2. 搜索附近的餐厅
        3. 推荐几家餐厅
        """
        query = "公司附近有什么好吃的餐厅推荐吗？"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"测试: 附近地点搜索")
        logger.info(f"用户: {query}")
        logger.info(f"{'='*60}")
        
        result = await run_smart_agent(query)
        
        logger.info(f"Agent回复: {result}")
        
        # 验证结果包含餐厅信息
        assert result is not None
        # Agent应该返回餐厅相关信息或表示无法搜索
        assert len(result) > 20

    @pytest.mark.asyncio
    async def test_only_ac_control(self):
        """
        测试：只调整空调
        
        用户说："把空调调到26度"
        Agent应该：
        1. 直接调整空调温度
        2. 确认调整结果
        """
        query = "把空调调到26度"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"测试: 空调控制")
        logger.info(f"用户: {query}")
        logger.info(f"{'='*60}")
        
        result = await run_smart_agent(query)
        
        logger.info(f"Agent回复: {result}")
        
        # 验证结果包含空调调整确认
        assert result is not None
        assert any(keyword in result for keyword in ["空调", "温度", "26", "调整"])

    @pytest.mark.asyncio
    async def test_morning_commute_full_scenario(self):
        """
        测试：完整的早高峰通勤场景（通用地点）
        
        场景：用户早上上班，需要先送小孩上学，再买咖啡，然后去公司
        地点：
        - 家：用户常用地点A
        - 学校：用户常用地点B
        - 咖啡：用户常用地点C
        - 公司：用户常用地点D
        
        Agent应该：
        1. 根据当前天气智能调整空调
        2. 规划包含多个途经点的路线
        3. 计算总耗时并判断能否9点前到达
        """
        # 模拟早上7:30出发
        query = "早上好！我现在准备出发去公司，要先送小孩去菲园幼儿园，然后去恒鼎大厦买杯瑞幸，最后到华为公司，帮我看看现在天气怎么样，调一下空调，再帮我规划下路线"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"测试: 完整早高峰通勤场景")
        logger.info(f"用户: {query}")
        logger.info(f"{'='*60}")
        
        result = await run_smart_agent(query)
        
        logger.info(f"Agent回复: {result}")
        
        # 验证结果的完整性
        assert result is not None
        assert len(result) > 100  # 完整回复应该比较长
        
        # 验证包含关键信息
        # 1. 天气信息
        has_weather = any(keyword in result for keyword in ["天气", "气温", "°C", "温度"])
        # 2. 空调信息
        has_ac = any(keyword in result for keyword in ["空调", "制热", "制冷", "温度"])
        # 3. 路线信息
        has_route = any(keyword in result for keyword in ["路线", "公里", "分钟", "到达"])
        
        logger.info(f"包含天气信息: {has_weather}")
        logger.info(f"包含空调信息: {has_ac}")
        logger.info(f"包含路线信息: {has_route}")
        
        # 至少应该包含路线信息
        assert has_route, "Agent应该规划路线"


class TestSmartAgentTimeSensitive:
    """测试时间敏感的场景"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """设置测试环境"""
        _ensure_test_env()

    @pytest.mark.asyncio
    async def test_different_departure_time_early(self):
        """
        测试：早出发（充裕时间）
        """
        query = "我准备7点出门去公司，要先送孩子上学再买咖啡，能9点前到吗？"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"测试: 早出发场景")
        logger.info(f"用户: {query}")
        logger.info(f"{'='*60}")
        
        result = await run_smart_agent(query)
        
        logger.info(f"Agent回复: {result}")
        
        assert result is not None
        # Agent应该给出时间判断
        assert any(keyword in result for keyword in ["到达", "分钟", "时间", "9点", "充裕", "可以"])

    @pytest.mark.asyncio
    async def test_different_departure_time_late(self):
        """
        测试：晚出发（时间紧张）
        """
        query = "我现在8点半才准备出门，还要送孩子上学和买咖啡，来得及9点到公司吗？"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"测试: 晚出发场景")
        logger.info(f"用户: {query}")
        logger.info(f"{'='*60}")
        
        result = await run_smart_agent(query)
        
        logger.info(f"Agent回复: {result}")
        
        assert result is not None
        # Agent应该分析时间是否充足
        assert any(keyword in result for keyword in ["分钟", "时间", "到达", "建议", "紧张", "来不及", "赶不上"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--log-cli-level=INFO"])
