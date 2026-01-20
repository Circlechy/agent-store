# ========== components.py示例代码 ==========
import setup_path
from config import create_model_config

from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.intent_detection_comp import IntentDetectionComponent, IntentDetectionCompConfig
from datetime import datetime
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from openjiuwen.core.component.questioner_comp import QuestionerComponent, QuestionerConfig, FieldInfo
from openjiuwen.core.component.tool_comp import ToolComponent, ToolComponentConfig
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.service_api.restful_api import RestfulApi


def create_start_component():
    """创建开始组件"""
    return Start({"inputs": [{"id": "query", "type": "String", "required": "true", "sourceType": "ref"}]})

def create_end_component():
    """创建结束组件"""
    return End({"responseTemplate": "{{output}}"})

def create_intent_detection_component() -> IntentDetectionComponent:
    """创建意图识别组件"""
    model_config = create_model_config()
    config = IntentDetectionCompConfig(
        user_prompt="请判断用户意图",
        category_name_list=["查询某地天气"],
        model=model_config,
    )
    return IntentDetectionComponent(config)

def build_current_date():
    current_datetime = datetime.now()
    return current_datetime.strftime("%Y-%m-%d")

def create_llm_component() -> LLMComponent:
    """创建 LLM 组件用于查询改写"""
    model_config = create_model_config()
    current_date = build_current_date()
    
    # 系统提示词模板
    SYSTEM_PROMPT_TEMPLATE = "你是一个query改写的AI助手。今天的日期是{}。"
    
    # 用户提示词，详细说明改写要求
    user_prompt = ("\n原始query为：{{query}}\n\n帮我改写原始query，要求：\n"
                   "1. 只把地名改为英文，其他信息保留中文；\n"
                   "2. 改写后的query必须包含当前的日期，默认日期为今天；\n"
                   "3. 日期为YYYY-MM-DD格式。")
    
    config = LLMCompConfig(
        model=model_config,
        template_content=[{"role": "user", "content": SYSTEM_PROMPT_TEMPLATE.format(current_date) + user_prompt}],
        response_format={"type": "json"},
        output_config={
            "rewritten_query": {"type": "string", "description": "改写后的query", "required": True}
        },
    )
    return LLMComponent(config)

def create_questioner_component() -> QuestionerComponent:
    """创建参数提取组件"""
    # 定义需要提取的字段
    key_fields = [
        FieldInfo(field_name="location", description="地点", required=True),
        FieldInfo(field_name="date", description="时间", required=True, default_value="today"),
    ]
    
    model_config = create_model_config()
    config = QuestionerConfig(
        model=model_config,
        question_content="",  # 直接从响应中提取字段
        extract_fields_from_response=True,
        field_names=key_fields,
        with_chat_history=False,
    )
    return QuestionerComponent(config)   

def create_plugin_component() -> ToolComponent:
    """创建天气查询插件组件"""
    tool_config = ToolComponentConfig()
    
    # 定义天气查询 RESTful API 工具
    weather_tool = RestfulApi(
        name="WeatherReporter",
        description="天气查询插件",
        params=[
            Param(name="location", description="地点", type="string", required=True),
            Param(name="date", description="日期", type="string", required=True),
        ],
        path="your weather service url",
        headers={},
        method="GET",
        response=[],
    )
    
    return ToolComponent(tool_config).bind_tool(weather_tool)
    