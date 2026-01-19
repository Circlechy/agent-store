"""
智能通勤Agent - 交互式入口

用户只需要用自然语言描述需求，Agent自己决定调用什么工具。

示例输入：
- "导航去公司，我希望九点之前到，要先去送一下小孩上学，然后顺道去买杯瑞幸"
- "今天天气怎么样？帮我调一下空调"
- "我要去华为上班，帮我规划路线"
- "查一下杭州今天的天气"

使用方法：
- python smart_agent.py                    # 交互模式（简洁输出）
- python smart_agent.py --verbose          # 交互模式（显示思考过程）
- python smart_agent.py --demo             # 演示模式
- python smart_agent.py "你的问题"          # 单次查询
"""
import asyncio
import json
import logging
import os
import sys
import dotenv

from prompts.template import apply_template

# 检查是否需要verbose模式（在导入框架之前检查）
_verbose_mode = '-v' in sys.argv or '--verbose' in sys.argv

# 如果非verbose模式，设置环境变量抑制框架日志
if not _verbose_mode:
    os.environ['JIUWEN_LOG_LEVEL'] = 'ERROR'
    os.environ['LOG_LEVEL'] = 'ERROR'
    # 抑制pydantic警告
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')
    # 抑制 langchain_tavily 库中的字段名冲突警告
    warnings.filterwarnings(
        'ignore',
        message='.*Field name.*shadows an attribute in parent.*',
        category=UserWarning
    )


class QuietStdout:
    """过滤掉框架日志的stdout包装器"""
    def __init__(self, stream, verbose=False):
        self.stream = stream
        self.verbose = verbose
        # 需要过滤的日志模式
        self.filter_patterns = [
            ' | common | ',
            ' | INFO |',
            ' | DEBUG |',
            '| _invoke_task |',
            '| checkpointer.py |',
            '| default_model.py |',
            '| manager.py |',
            '| emitter.py |',
            '| base.py |',
            '[TOOL START]',
            '[TOOL END]',
            '[TOOL ARGS]',
            '[TOOL ERROR]',
            '[TOOL RECOVERY]',
        ]
    
    def write(self, text):
        if self.verbose:
            self.stream.write(text)
            return
        
        # 检查是否需要过滤
        should_filter = any(pattern in text for pattern in self.filter_patterns)
        if not should_filter:
            self.stream.write(text)
    
    def flush(self):
        self.stream.flush()
    
    def __getattr__(self, name):
        return getattr(self.stream, name)


# 非verbose模式下包装stdout
if not _verbose_mode:
    sys.stdout = QuietStdout(sys.stdout, verbose=False)

dotenv.load_dotenv(dotenv_path=".env")

def _assert_required_env():
    required_keys = [
        "MODEL_PROVIDER",
        "API_BASE",
        "API_KEY",
        "MODEL_NAME",
        "TAVILY_API_KEY",
        "EMBED_API_BASE",
        "EMBED_API_KEY",
        "EMBED_MODEL_NAME",
    ]
    missing = [key for key in required_keys if not os.getenv(key)]
    if missing:
        missing_list = ", ".join(missing)
        raise RuntimeError(
            f"缺少必要环境变量: {missing_list}。"
            "请根据 .env.example 配置 .env 后重试。"
        )

_assert_required_env()

# 全局verbose标志
VERBOSE = False

def setup_logging(verbose: bool = False):
    """配置日志级别"""
    global VERBOSE
    VERBOSE = verbose
    
    # 始终记录到文件
    file_handler = logging.FileHandler('run.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # 控制台输出级别取决于verbose
    console_handler = logging.StreamHandler()
    if verbose:
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    else:
        # 静默模式：只显示ERROR
        console_handler.setLevel(logging.ERROR)
    
    # 配置根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = []
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 特别静默一些库的日志（非verbose模式）
    if not verbose:
        for logger_name in ['httpx', 'common', 'openjiuwen', 'nodes', 'tools', 
                           'openjiuwen.core', 'urllib3', 'asyncio']:
            logging.getLogger(logger_name).setLevel(logging.ERROR)

from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.graph.executable import Input, Output
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.runtime.workflow import WorkflowRuntime
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory

from nodes.smart_commute_agent import SmartCommuteAgent
from nodes.multi_agent import MultiAgent
from nodes.base_node import init_router
from tools.tts import auto_speak_response

logger = logging.getLogger(__name__)
factory = ModelFactory()
model_name = os.getenv("MODEL_NAME")
model = factory.get_model(
    model_provider=os.getenv("MODEL_PROVIDER"),
    api_base=os.getenv("API_BASE"),
    api_key=os.getenv("API_KEY"),
    max_retries=3,
    timeout=600,
)

def _ensure_update_global_state(runtime):
    if hasattr(runtime, "update_global_state"):
        return

    def _update_global_state(updates: dict):
        state = runtime.state() if hasattr(runtime, "state") else None
        if state is None:
            raise AttributeError("Runtime has no state()")

        # 尝试不同的状态更新方法
        if hasattr(state, "update_global_state"):
            try:
                return state.update_global_state(updates)
            except TypeError:
                pass
        if hasattr(state, "update_global"):
            try:
                return state.update_global(updates)
            except TypeError:
                for key, value in updates.items():
                    state.update_global(key, value)
                return None
        if hasattr(state, "set_global"):
            try:
                return state.set_global(updates)
            except TypeError:
                for key, value in updates.items():
                    state.set_global(key, value)
                return None

        # 最后兜底：逐个属性更新
        for key, value in updates.items():
            if hasattr(state, "set"):
                try:
                    state.set(key, value)
                    continue
                except Exception:
                    pass
            raise AttributeError("State does not support global updates")

    setattr(runtime, "update_global_state", _update_global_state)


class StartNode(Start):
    """启动节点"""
    def __init__(self, query: str, history_messages: list = None, user_id: str = "default_user", 
                 enable_long_term_memory: bool = False, image_data: str = None, speaker_info: dict = None,
                 force_next_node: str = None):
        super().__init__()
        self.query = query
        self.history_messages = history_messages or []
        self.user_id = user_id
        self.enable_long_term_memory = enable_long_term_memory
        self.image_data = image_data
        self.speaker_info = speaker_info
        self.force_next_node = force_next_node
    
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        runtime.update_global_state({"language": "Chinese"})
        runtime.update_global_state({"query": self.query})
        runtime.update_global_state({"messages": self.history_messages})
        runtime.update_global_state({"user_id": self.user_id})
        runtime.update_global_state({"enable_long_term_memory": self.enable_long_term_memory})
        if self.image_data:
            runtime.update_global_state({"current_image_data": self.image_data})
        if self.speaker_info:
            runtime.update_global_state({"speaker_info": self.speaker_info})

        if self.force_next_node:
            next_node = self.force_next_node
        else:
            router_input = {
                "current_query": self.query,
            }
            router_prompt = apply_template("smart_router", router_input)

            response = await model.ainvoke(model_name=model_name, messages=router_prompt)
            raw_content = response.model_dump(exclude_none=True).get("content", "").strip()
            router_result = json.loads(raw_content)
            next_node = router_result.get("next_node", "smart_agent")

        logger.info(f"{self.query} StartNode Router Result: {next_node}")

        if next_node == "smart_agent":
            return dict(next_node="smart_agent")
        elif next_node == "multi_agent":
            return dict(next_node="multi_agent")
        else:
            logger.warning(f"路由节点返回了意外的内容: {next_node}，将使用默认值 'smart_agent'")
            return dict(next_node="smart_agent")


class EndNode(End):
    """结束节点"""
    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        result = runtime.get_global_state("result")
        print("\n" + "="*60)
        print("🚗 智能车载助手回复：")
        print("="*60)
        print(result)
        print("="*60 + "\n")
        if result:
            try:
                tts_playback = runtime.get_global_state("tts_playback")
                # 当由浏览器端负责播报时，避免服务端本地播报
                if tts_playback not in ("browser", "browser_audio"):
                    auto_speak_response(result)
            except Exception as e:
                logger.debug(f"自动TTS播报失败: {e}")
        return inputs


def build_smart_agent_workflow(query: str, history_messages: list = None, 
                                user_id: str = "default_user",
                                enable_long_term_memory: bool = False,
                                image_data: str = None,
                                speaker_info: dict = None,
                                force_next_node: str = None) -> Workflow:
    """构建智能Agent工作流"""
    
    config = WorkflowConfig(
        metadata=WorkflowMetadata(
            name="Smart Commute Agent",
            description="智能通勤Agent - 用户自然语言输入，Agent自主决定调用工具"
        ),
        inputs_schema=WorkflowInputsSchema(properties={}, required=[])
    )
    
    workflow = Workflow(workflow_config=config)
    workflow.set_start_comp(
        "start",
        StartNode(
            query,
            history_messages,
            user_id,
            enable_long_term_memory,
            image_data,
            speaker_info,
            force_next_node,
        ),
    )
    workflow.add_workflow_comp("smart_agent", SmartCommuteAgent())
    workflow.add_workflow_comp("multi_agent", MultiAgent())
    workflow.set_end_comp("end", EndNode())

    router = init_router("start", ["smart_agent", "multi_agent"])
    
    workflow.add_conditional_connection("start", router=router)
    workflow.add_connection("smart_agent", "end")
    workflow.add_connection("multi_agent", "end")
    
    return workflow


async def run_agent(query: str, history_messages: list = None, 
                    user_id: str = "default_user",
                    enable_long_term_memory: bool = False,
                    image_data: str = None,
                    speaker_info: dict = None,
                    force_next_node: str = None,
                    event_emitter: callable = None,
                    tts_playback: str = None) -> tuple:
    """运行智能Agent
    
    Args:
        query: 用户输入
        history_messages: 历史对话消息列表
        user_id: 用户ID（用于长期记忆）
        enable_long_term_memory: 是否启用长期记忆
        image_data: 图片数据（base64格式，可选）
        speaker_info: 说话者信息（包含name, seat等）
        
    Returns:
        tuple: (result, updated_history_messages, tool_trace)
    """
    workflow = build_smart_agent_workflow(
        query,
        history_messages,
        user_id,
        enable_long_term_memory,
        image_data,
        speaker_info,
        force_next_node,
    )
    runtime = WorkflowRuntime()
    _ensure_update_global_state(runtime)
    if event_emitter:
        runtime.update_global_state({"event_emitter": event_emitter})
    if tts_playback:
        runtime.update_global_state({"tts_playback": tts_playback})
    
    await workflow.invoke(inputs={}, runtime=runtime, context=None)
    
    result = runtime.state().get_global("result")
    updated_messages = runtime.state().get_global("messages")
    tool_trace = runtime.state().get_global("tool_trace") or []
    
    return result, updated_messages, tool_trace


async def interactive_mode(enable_memory: bool = False, user_id: str = None, force_next_node: str = None):
    """交互模式 - 支持多轮对话上下文和长期记忆"""
    import uuid
    
    # 生成或使用用户ID
    if user_id is None:
        user_id = f"user_{uuid.uuid4().hex[:8]}"
    
    print("\n" + "="*60)
    print("🚗 欢迎使用智能车载通勤助手！")
    print("="*60)
    if enable_memory:
        print(f"📝 长期记忆已启用 (用户ID: {user_id})")
    print("你可以用自然语言告诉我你的需求，例如：")
    print("  - '导航去公司，九点前到，先送小孩上学，再买杯瑞幸'")
    print("  - '今天天气怎么样？帮我调一下空调'")
    print("  - '从家到公司怎么走最快？'")
    print("  - '帮我查一下最近有什么八卦新闻'")
    print("\n输入 'exit' 或 '退出' 结束对话")
    print("输入 'clear' 或 '清空' 清除对话历史")
    print("="*60 + "\n")
    
    # 维护对话历史
    history_messages = []
    
    while True:
        try:
            query = input("👤 你: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['exit', '退出', 'quit', 'q']:
                print("\n👋 再见！祝您一路顺风！\n")
                break
            
            if query.lower() in ['clear', '清空', 'reset']:
                history_messages = []
                print("\n🔄 对话历史已清空，开始新的对话\n")
                continue
            
            print("\n🤔 思考中...\n")
            result, history_messages, _ = await run_agent(
                query, 
                history_messages, 
                user_id=user_id,
                enable_long_term_memory=enable_memory,
                force_next_node=force_next_node,
            )
            
        except KeyboardInterrupt:
            print("\n\n👋 再见！\n")
            break
        except Exception as e:
            logger.error(f"执行出错: {e}")
            print(f"\n❌ 抱歉，出现了一些问题: {e}\n")


async def demo_mode():
    """演示模式 - 运行预设的测试用例（支持多轮对话）"""
    
    # 演示多轮对话
    test_conversations = [
        [
            "帮我查一下最近有什么八卦新闻，在路上讲给我听",
            "这个新闻里提到的明星是谁？",
        ],
        [
            "导航去公司，我希望九点之前到，要先去送一下小孩上学，然后顺道去买杯瑞幸",
        ],
    ]
    
    print("\n" + "="*60)
    print("🚗 智能车载通勤助手 - 演示模式（多轮对话）")
    print("="*60 + "\n")
    
    for conv_idx, conversation in enumerate(test_conversations, 1):
        print(f"\n{'='*60}")
        print(f"📝 对话场景 {conv_idx}:")
        print("="*60)
        
        history = []
        for turn_idx, query in enumerate(conversation, 1):
            print(f"\n👤 用户 (第{turn_idx}轮): {query}")
            result, history, _ = await run_agent(query, history)
        
        if conv_idx < len(test_conversations):
            print("\n" + "-"*40 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='🚗 智能车载通勤助手')
    parser.add_argument('query', nargs='*', help='直接输入问题进行单次查询')
    parser.add_argument('--demo', action='store_true', help='运行演示模式')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细思考过程')
    parser.add_argument('--no-memory', action='store_true', help='禁用长期记忆功能（默认启用）')
    parser.add_argument('--user-id', type=str, default=None, help='指定用户ID（用于长期记忆）')
    parser.add_argument('--multi-agent', action='store_true', help='强制走MultiAgent流程（测试用）')
    
    args = parser.parse_args()
    
    # 设置日志级别
    setup_logging(verbose=args.verbose)
    
    async def single_query_mode(query: str, enable_memory: bool = False, user_id: str = None, force_next_node: str = None):
        """单次查询模式"""
        await run_agent(
            query,
            enable_long_term_memory=enable_memory,
            user_id=user_id or "default_user",
            force_next_node=force_next_node,
        )
    
    # 默认启用记忆，除非明确禁用
    enable_memory = not args.no_memory
    
    if args.demo:
        # 演示模式
        asyncio.run(demo_mode())
    elif args.query:
        # 单次查询模式
        query = " ".join(args.query)
        force_next_node = "multi_agent" if args.multi_agent else None
        asyncio.run(single_query_mode(query, enable_memory, args.user_id, force_next_node))
    else:
        # 交互模式
        force_next_node = "multi_agent" if args.multi_agent else None
        asyncio.run(interactive_mode(enable_memory=enable_memory, user_id=args.user_id, force_next_node=force_next_node))
