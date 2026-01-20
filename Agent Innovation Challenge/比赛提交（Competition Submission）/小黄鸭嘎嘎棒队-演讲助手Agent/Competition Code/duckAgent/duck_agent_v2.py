#!/usr/bin/env python
# coding: utf-8
"""
DuckAgent v3 - 主线程运行 TK，通过管道接收命令
重构版本：将一次性操作从工作流中提取，集中到主函数控制
"""

import os
import sys
import asyncio
import threading
import queue
import time

# 添加项目路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# 导入核心组件
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata
from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.core.runner.runner import Runner

# 导入工具组件
from speech_recognition import SpeechRecognitionComponent
from text_matching import TextMatchingComponent
from window_drawing import WindowDrawingComponent
from speech_timing import ElementTimingManager
from main_thread_timing import MainThreadTimingManager
import dashscope

# 配置环境变量
os.environ.setdefault("API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
os.environ.setdefault("API_KEY", "sk-88abf93140a949adbacd394683f33811")
os.environ.setdefault("MODEL_PROVIDER", "openai")
os.environ.setdefault("MODEL_NAME", "qwen3-max")
os.environ.setdefault("LLM_SSL_VERIFY", "false")

dashscope.api_key = os.environ.get("API_KEY")
dashscope.base_websocket_api_url = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"


def load_config():
    """加载配置"""
    return {
        "API_BASE": os.getenv("API_BASE"),
        "API_KEY": os.getenv("API_KEY"),
        "MODEL_PROVIDER": os.getenv("MODEL_PROVIDER"),
        "MODEL_NAME": os.getenv("MODEL_NAME"),
        "LLM_SSL_VERIFY": os.getenv("LLM_SSL_VERIFY", "false"),
    }


def create_model_config(config):
    """创建模型配置"""
    return ModelConfig(
        model_provider=config["MODEL_PROVIDER"],
        model_info=BaseModelInfo(
            api_key=config["API_KEY"],
            api_base=config["API_BASE"],
            model=config["MODEL_NAME"],
        ),
    )


def create_start_component():
    """创建开始组件"""
    return Start(
        {
            "inputs": [
                {
                    "id": "ppt_data",
                    "type": "Object",
                    "required": "true",
                    "sourceType": "ref",
                }
            ]
        }
    )


def create_llm_component(model_config):
    """创建LLM组件"""
    SYSTEM_PROMPT = "你是一个智能问答助手。"
    USER_PROMPT = "{{query}}"
    config = LLMCompConfig(
        model=model_config,
        template_content=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT},
        ],
        response_format={"type": "text"},
        output_config={"answer": {"type": "string", "required": True}},
    )
    return LLMComponent(config)


def create_end_component():
    """创建结束组件"""
    return End({"responseTemplate": "{{output}}"})


def create_workflow(model_config):
    """创建工作流（不含一次性操作组件）"""
    workflow_config = WorkflowConfig(
        metadata=WorkflowMetadata(name="duck_qa", id="duck_qa_agent", version="1.0")
    )
    flow = Workflow(workflow_config=workflow_config)

    start = create_start_component()
    speech_recognition = SpeechRecognitionComponent()
    text_matching = TextMatchingComponent()
    window_drawing = WindowDrawingComponent()
    end = create_end_component()

    # 注册组件
    flow.set_start_comp("start", start, inputs_schema={"ppt_data": "${ppt_data}"})
    flow.add_workflow_comp(
        "speech_recognition",
        speech_recognition,
        inputs_schema={"input_data": "${start.ppt_data.audio_path}"},
    )
    flow.add_workflow_comp(
        "text_matching",
        text_matching,
        stream_inputs_schema={
            "recog_sentence": "${speech_recognition.recog_sentence}",
            "ppt_data": "${start.ppt_data}",
        },
    )
    flow.add_workflow_comp(
        "window_drawing",
        window_drawing,
        stream_inputs_schema={"input_data": "${text_matching.matched_elements}"},
    )
    flow.set_end_comp("end", end, inputs_schema={"output": "演讲辅助完成"})

    # 添加连接
    flow.add_connection("start", "speech_recognition")
    flow.add_stream_connection("speech_recognition", "text_matching")
    flow.add_stream_connection("text_matching", "window_drawing")
    flow.add_connection("window_drawing", "end")
    return flow


def create_and_bind_agent(flow):
    """创建并绑定Agent"""
    schema = WorkflowSchema(
        id=flow.config().metadata.id,
        name=flow.config().metadata.name,
        version=flow.config().metadata.version,
        inputs={"ppt_data": {"type": "object"}},
    )
    agent_config = WorkflowAgentConfig(
        id="duck_qa_agent", version="1.0.0", workflows=[schema]
    )
    workflow_agent = WorkflowAgent(agent_config)
    workflow_agent.bind_workflows([flow])
    return workflow_agent


# ========== 一次性操作 ==========


def init_ppt():
    """
    初始化PPT解析（一次性操作）
    从工作流中提取的PPT解析操作
    """
    print("📊 [一次性操作] 初始化PPT解析...")

    # 导入PPT解析器和元素匹配器
    from tools.ppt_parser import PPTDataParser
    from tools.element_matcher import ElementMatcher

    # 创建并初始化PPT解析器
    ppt_parser = PPTDataParser()

    # 解析PPT文件
    ppt_path = os.path.join("./samples", "harmonyOS.pptx")

    print(f"📊 [一次性操作] 解析PPT文件：{ppt_path}")
    ppt_parser.parse_ppt(ppt_path=ppt_path)

    # 获取解析结果
    text_elems = ppt_parser.get_elem_texts()
    elem_coords = ppt_parser.get_elem_coords()

    # 转换键为字符串类型，确保与工作流系统兼容
    text_elems_str_keys = {str(key): value for key, value in text_elems.items()}
    elem_coords_str_keys = {str(key): value for key, value in elem_coords.items()}

    # 核心修复：初始化ElementMatcher数据
    try:
        ElementMatcher.init_data(elem_texts=text_elems_str_keys, match_threshold=0.6)
        print("📊 [一次性操作] ElementMatcher数据初始化成功")
    except Exception as e:
        print(f"📊 [一次性操作] ElementMatcher数据初始化失败：{e}")
        raise

    # 构建标准Element格式
    elements = []
    for idx, text in text_elems_str_keys.items():
        # 根据内容简单判断element_type
        element_type = "unknown"
        text_lower = text.lower()
        if len(text) < 20 and any(
            keyword in text_lower for keyword in ["标题", "title", "主题"]
        ):
            element_type = "title"
        elif len(text) > 50 and any(
            keyword in text_lower for keyword in ["论点", "核心", "core", "argument"]
        ):
            element_type = "core_argument"
        elif any(keyword in text_lower for keyword in ["案例", "case", "example"]):
            element_type = "case"
        elif any(
            keyword in text_lower for keyword in ["图表", "chart", "graph", "figure"]
        ):
            element_type = "chart"
        elif any(
            keyword in text_lower
            for keyword in ["总结", "summary", "结论", "conclusion"]
        ):
            element_type = "summary"

        element = {
            "element_id": idx,
            "element_type": element_type,
            "content": text,
            "page_num": 1,  # 简化处理，假设所有元素都在第1页
            "script_paragraph": text,  # 使用内容作为脚本段落
        }
        elements.append(element)

    # 设置总演讲时间（默认5分钟）
    total_speech_seconds = 50
    print(f"⏰ [一次性操作] 设置总演讲时间：{total_speech_seconds}s")

    # 初始化ElementTimingManager并计算理论时长
    timing_manager = ElementTimingManager()
    updated_elements, element_timing_map = timing_manager.calculate_element_timings(
        elements, total_speech_seconds
    )

    print(f"📊 [一次性操作] PPT解析完成，共{len(text_elems_str_keys)}个文本元素")
    for idx, text in text_elems_str_keys.items():
        print(f"  元素{idx}：{text}")

    # 获取音频文件路径
    audio_path = os.path.join(
        "./samples",
        "harmonyOS.mp3",
    )

    return {
        "parser": ppt_parser,
        "text_elems": text_elems_str_keys,
        "elem_coords": elem_coords_str_keys,
        "ppt_path": ppt_path,
        "audio_path": audio_path,
        "elements": updated_elements,
        "element_timing_map": element_timing_map,
        "total_speech_seconds": total_speech_seconds,
    }


def init_window(ppt_data):
    """
    初始化窗口（一次性操作）
    从工作流中提取的窗口初始化操作
    """
    print("🖼️ [一次性操作] 初始化窗口...")

    # 导入高亮渲染器
    from tools.highlight_renderer import HighlightRenderer

    # 预初始化TK窗口
    renderer = HighlightRenderer.pre_init()

    # 核心修复：设置元素坐标
    try:
        elem_coords = ppt_data.get("elem_coords", {})
        if elem_coords:
            renderer.set_elem_coords(elem_coords)
            print("🖼️ [一次性操作] 元素坐标设置成功")
            print(f"🖼️ [一次性操作] 共设置 {len(elem_coords)} 个元素坐标")
        else:
            print("🖼️ [一次性操作] 未找到元素坐标数据")
    except Exception as e:
        print(f"🖼️ [一次性操作] 设置元素坐标失败：{e}")

    print("🖼️ [一次性操作] 窗口初始化完成")

    return renderer


# ========== Agent管理器 ==========


class AgentManager:
    """在后台线程管理 Agent 执行"""

    def __init__(self, agent, ppt_data):
        self.agent = agent
        self.ppt_data = ppt_data
        self.command_queue = queue.Queue()
        self.running = True

    def start(self):
        """启动 Agent 管理线程"""
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()
        print("✅ Agent 管理线程已启动")

    def _run_loop(self):
        """后台循环：处理命令队列"""
        while self.running:
            try:
                # 非阻塞检查命令
                command = self.command_queue.get(timeout=0.1)

                if command == "exit":
                    break

                # 运行 Agent
                print(f"\n[Agent] 处理命令: {command}")
                self._run_agent()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"\n[Agent] 错误: {e}")

    def _run_agent(self):
        """执行 Agent"""
        start_time = time.time()
        print(f"\n[Agent] 开始执行")
        print(
            f"[Timer] 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 传递PPT数据给Agent
            agent_start = time.time()
            print(f"[Timer] Agent执行开始: {agent_start - start_time:.2f}s")

            result = loop.run_until_complete(
                Runner.run_agent(self.agent, {"ppt_data": self.ppt_data})
            )

            agent_end = time.time()
            print(f"[Timer] Agent执行结束: {agent_end - start_time:.2f}s")
            print(f"[Timer] Agent执行耗时: {agent_end - agent_start:.2f}s")

            # 处理结果
            if result and hasattr(result, "get"):
                output = result.get("output")
                if output and hasattr(output, "result"):
                    response = output.result.get("responseContent", "完成")
                    print(f"\n[Agent] 回答: {response}")
                else:
                    print(f"\n[Agent] 完成")
            else:
                print(f"\n[Agent] 完成")

        except Exception as e:
            error_time = time.time()
            print(f"\n[Agent] 执行错误: {e}")
            print(f"[Timer] 错误发生时间: {error_time - start_time:.2f}s")
            import traceback

            traceback.print_exc()
        finally:
            end_time = time.time()
            print(f"[Timer] 总执行时间: {end_time - start_time:.2f}s")
            print(
                f"[Timer] 结束时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
            )
            loop.close()

    def send_command(self, command):
        """发送命令到队列"""
        self.command_queue.put(command)

    def stop(self):
        """停止管理器"""
        self.running = False
        self.command_queue.put("exit")


def check_stdin_input(agent_manager, root):
    """定期检查标准输入（通过 after 调度）"""
    import select

    # 检查是否有输入
    if sys.platform != "win32":
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if ready:
            try:
                line = sys.stdin.readline().strip()
                if line:
                    if line.lower() == "exit":
                        print("\n退出程序...")
                        root.quit()
                        return
            except:
                pass

    # 继续调度
    root.after(100, lambda: check_stdin_input(agent_manager, root))


# ========== 主函数 ==========


def main():
    """
    主函数：集中控制所有一次性操作
    1. 初始化PPT解析（一次性）
    2. 初始化窗口（一次性）
    3. 创建工作流和Agent
    4. 启动后台线程处理用户输入
    5. 运行TK主循环
    """
    print("=" * 60)
    print("DuckAgent v3 - PPT 演讲辅助系统")
    print("=" * 60)

    # 1. 执行一次性操作：初始化PPT解析
    ppt_data = init_ppt()

    # 2. 执行一次性操作：初始化窗口
    renderer = init_window(ppt_data)

    # 3. 创建工作流和Agent
    config = load_config()
    model_config = create_model_config(config)
    flow = create_workflow(model_config)
    print(f"创建工作流: {flow.config().metadata.id}")

    agent = create_and_bind_agent(flow)
    print(f"创建智能体: {agent.agent_config.id}")

    # 4. 初始化主线程计时管理器
    timing_manager = MainThreadTimingManager.get_instance()
    timing_manager.initialize(ppt_data["element_timing_map"], renderer)
    print("⏰ [系统] 主线程计时管理器已初始化")

    # 5. 启动Agent管理器（后台线程）
    agent_manager = AgentManager(agent, ppt_data)
    agent_manager.start()

    print("=" * 60)
    print("✅ 高亮窗口已启动（全屏透明）")
    print("⏰ 计时显示已在左上角启动")
    print("💡 系统将自动执行workflow分析")
    print("=" * 60)

    # 6. 启动全局计时
    timing_manager.start_timing()
    print("\n[系统] 全局计时已启动")

    # 7. 定期检查计时（主线程）
    def periodic_timing_check():
        if agent_manager.running:
            timing_manager.check_timing()
            renderer.root.after(2000, periodic_timing_check)  # 每2秒检查一次

    renderer.root.after(2000, periodic_timing_check)
    print("[系统] 定期计时检查已启动")

    # 自动执行一次workflow
    print("\n[系统] 自动启动workflow执行...")
    agent_manager.send_command("start")

    # 5. 使用 after 定期检查输入（仅用于退出）
    renderer.root.after(100, lambda: check_stdin_input(agent_manager, renderer.root))

    # 6. 主线程运行 TK 主循环
    try:
        renderer.root.mainloop()
    finally:
        agent_manager.stop()
        print("\n程序已退出")


if __name__ == "__main__":
    main()
