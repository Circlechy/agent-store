# ========== 参考components.py示例代码 ==========
# **重要说明**：生成components.py时，必须将所有import语句集中在文件开头，不要分散在各个组件示例中

# ========== 导入语句（必须放在文件开头） ==========
import setup_path
from config import create_model_config

# 组件导入（根据实际使用的组件类型，选择需要的导入）
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from openjiuwen.core.component.questioner_comp import FieldInfo, QuestionerConfig, QuestionerComponent
from openjiuwen.core.component.intent_detection_comp import IntentDetectionComponent, IntentDetectionCompConfig
from openjiuwen.core.component.tool_comp import ToolComponent, ToolComponentConfig
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.utils.tool.service_api.restful_api import RestfulApi
from openjiuwen.core.component.branch_comp import BranchComponent
from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runtime.base import ComponentExecutable, Input, Output
from openjiuwen.core.runtime.runtime import Runtime

# ========== 组件创建函数示例 ==========

# 1. Start组件示例（固定格式）
def create_start_component():
    """创建开始组件"""
    return Start({"inputs": [{"id": "query", "type": "String", "required": "true", "sourceType": "ref"}]})

# **重要说明**：
# - 创建Start组件时，固定采用上述格式
# - **强制要求**：Start组件的输入变量名**必须为query，禁止使用其他任何值**（如user_input、text、message等）
# - **错误示例**（禁止出现）：
#   - Start({"inputs": [{"id": "user_input", ...}]})  # 错误：变量名必须是query
#   - Start({"inputs": [{"id": "text", ...}]})  # 错误：变量名必须是query
# - **正确示例**：
#   - Start({"inputs": [{"id": "query", "type": "String", "required": "true", "sourceType": "ref"}]})  # 正确
 
# 2. End组件示例
def create_end_component():
    """创建结束组件"""
    return End({"responseTemplate": "{{output}}"})

# **重要说明**：
# - End 组件创建时，固定使用形如 {"responseTemplate": "{{output}}"}的字典，字典有且仅有responseTemplate，没有其他字段。
# - 字典的值表示End组件输出的内容，可以有多种格式。
# 格式1：直接输出字符串，如{"responseTemplate": "工作流运行完成"}
# 格式2：只输出End组件输入变量的内容，如{"responseTemplate": "{{output}}"}，表示End组件直接输出output字段的内容，output为End组件的输入变量。
# 格式3：输出字符串和输入变量的结合内容，如{"responseTemplate": "最终结果输出：{{output}}"}。
# 格式4：输出字符串和多个输入变量的结合内容，如{"responseTemplate": "推荐产品：{{product}}, 推荐理由：{{reason}}"}。product和reason为End组件的输入变量。
# 格式5：输出不同分支的内容，如{"responseTemplate": "{{result1}}{{result2}}"}。result1和result2均为End组件的输入变量，result1和result2分别对应不同分支的输出。
# **重要说明**：需要根据工作流的实际情况确定End组件会接收哪些变量，需要将这些变量都列出来，不能遗漏。
# **正确示例**：
# - End({"responseTemplate": "{{result1}}{{result2}}"})  # 正确：result1和result2分别对应不同分支的输出
# - responseTemplate 如果要引用变量，必须使用双花括号格式：{{output}}，不能使用单花括号格式：{output}
# **错误示例**（禁止出现）：
# - End({"responseTemplate": "{output}"})  # 错误：使用了单花括号
# - End({"responseTemplate": "{{output}}", "inputs": [...]}})  # 错误：End 组件不应该有 responseTemplate 之外的其他字段

# 3. LLMComponent 示例
def create_llm_component() -> LLMComponent:
    """创建 LLM 组件"""
    system_prompt = "你是一个处理用户查询的AI助手。"
    user_prompt = "{{query}}"
    config = LLMCompConfig(
        model=create_model_config(),
        template_content=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        response_format={"type": "json"},
        output_config={
            "output": {"type": "string", "description": "处理结果", "required": True}
        },
    )
    return LLMComponent(config)

# **重要说明**：
# - 创建LLMComponent组件时，固定采用上述格式
# - system_prompt 为系统提示词，根据实际需求编写
# - user_prompt 为用户提示词，根据实际需求编写，{{query}}表示引用当前LLM组件的输入变量query的值，必须使用双花括号格式：{{query}}，不能使用单花括号格式：{query}
# - 在user_prompt中，可以引用多个输入变量，例如：{{query}}，{{location}}，{{date}}，表示引用当前LLM组件的输入变量query、location和date的值
# - 禁止直接引用其他组件的输出变量，如采用{{component_id.field}}的形式，错误示例：{{start.query}}
# - model 必须使用 create_model_config() 函数创建的大模型配置，不能使用其他方式创建的大模型配置
# - template_content 采用示例中的固定模式，不能修改
# - response_format 必须使用 {"type": "json"}
# - output_config 配置了该组件的所有输出变量，示例中表示输出一个字符串类型的变量output，描述为处理结果，必须输出。
# 如果需要输出多个变量，则仿照示例中的格式，添加新的字段即可。例如：输出两个字符串类型的变量output1和output2，描述分别为处理结果1和处理结果2，必须输出。则output_config应为：
# output_config = {
#     "output1": {"type": "string", "description": "处理结果1", "required": True},
#     "output2": {"type": "string", "description": "处理结果2", "required": True},
# }

# 4. QuestionerComponent 示例
def create_questioner_component() -> QuestionerComponent:
    """创建提问组件"""
    # FieldInfo描述了需要提取的参数信息，包含参数名field_name、参数描述信息description、是否必须提取required以及参数默认值default_value。如果是必选参数且没有默认值，就必须提取该待提取参数的值。
    key_fields = [
        FieldInfo(field_name="location", description="地点", required=True),
        FieldInfo(field_name="date", description="时间", required=True, default_value="today"),
    ]
    config = QuestionerConfig(
        model = create_model_config(),
        question_content="",
        extract_fields_from_response=True,
        field_names=key_fields,
        with_chat_history=False,
        extra_prompt_for_fields_extraction="开发者自定义的参数提取的约束",
        example_content="开发者自定义的样例"
    )
    return QuestionerComponent(config)

# **重要说明**：
# - 创建QuestionerComponent组件时，固定采用上述格式
# - model 必须使用 create_model_config() 函数创建的大模型配置，不能使用其他方式创建的大模型配置
# - extract_fields_from_response 必须为True，不能修改
# - field_names 为需要提取的参数信息，示例中表示提取两个参数：location和date，必须提取。如果需要提取多个参数，则仿照示例中的格式，添加新的字段即可。
# - **关键：question_content 控制提问器组件的两种工作模式**
#   **模式1：智能提取模式（question_content为空字符串""）**
#   - 作用：从用户输入中智能提取变量
#   - 工作方式：
#     * 如果用户输入中已经包含所需变量的信息，则直接执行提取操作，不会向用户提问
#     * 如果用户输入中没有包含所需变量的信息，则向用户提问，再从用户回复中提取变量
#   - 适用场景：需要从用户输入中提取参数的工作流（如温度调节、地点查询等）
#   - 示例：温度调节工作流
#     * 用户输入"把温度调整成25度" → 提问器直接提取到温度信息（25度），不会提问
#     * 用户输入"调整温度" → 提问器询问"请告诉我要调整到多少度？"，从用户回复中提取温度信息
#   - 代码示例：
#     ```python
#     config = QuestionerConfig(
#         model=create_model_config(),
#         question_content="",  # 空字符串，智能提取模式
#         extract_fields_from_response=True,
#         field_names=[FieldInfo(field_name="temperature", description="目标温度", required=True)],
#         ...
#     )
#     ```
#   **模式2：调查模式（question_content不为空）**
#   - 作用：作为调查功能，主动向用户提问
#   - 工作方式：
#     * 不管用户输入中有没有包含变量信息，都必然触发提问
#     * 提问器会询问用户问题，然后从用户回复中提取变量
#   - 适用场景：问卷调查、信息收集等工作流
#   - 示例：问卷调查工作流
#     * 无论用户输入什么，提问器都会询问"请回答以下问题：您最喜欢的颜色是什么？"
#     * 从用户回复中提取答案
#   - 代码示例：
#     ```python
#     config = QuestionerConfig(
#         model=create_model_config(),
#         question_content="请回答以下问题：您最喜欢的颜色是什么？",  # 非空，调查模式
#         extract_fields_from_response=True,
#         field_names=[FieldInfo(field_name="favorite_color", description="最喜欢的颜色", required=True)],
#         ...
#     )
#     ```
#   **选择原则**：
#   - 如果工作流需要从用户输入中智能提取参数（如温度、地点、日期等），使用模式1（question_content=""）
#   - 如果工作流需要主动向用户提问进行调查（如问卷调查、信息收集等），使用模式2（question_content="具体问题内容"）
#   - 必须根据要创建的工作流情况，确定question_content的内容

# 5. IntentDetectionComponent 示例
def create_intent_detection_component() -> IntentDetectionComponent:
    """创建意图识别组件"""
    config = IntentDetectionCompConfig(
        user_prompt="请判断用户意图",
        category_name_list=["查询某地天气"],
        model=create_model_config(),
    )
    return IntentDetectionComponent(config)

# **重要说明**：
# - 创建IntentDetectionComponent组件时， 固定采用上述格式
# - user_prompt 为用户提示词，根据实际需求编写，用于提示大模型更好地识别用户意图。
# - category_name_list 为意图分类列表，除列表中的内容外，会默认添加一个默认分类；如果需要分类多个意图，则仿照示例中的格式，添加新的分类即可。
# - model 必须使用 create_model_config() 函数创建的大模型配置，不能使用其他方式创建的大模型配置。

# 6. ToolComponent 示例
def create_plugin_component() -> ToolComponent:
    """创建天气查询插件组件"""
    tool_config = ToolComponentConfig()
    
    # 定义天气查询 RESTful API 工具
    weather_tool = RestfulApi(
        name="mock_weather",
        description="模拟天气查询接口，返回固定的模拟天气数据，用于测试",
        params=[
            Param(name="location", description="地点", type="string", required=True),
            Param(name="date", description="日期", type="string", required=True),
        ],
        path="http://127.0.0.1:9000/mock_weather",
        headers={},
        method="GET",
        response=[],
    )
    
    return ToolComponent(tool_config).bind_tool(weather_tool)

# **重要说明**：
# - 使用ToolComponent 必须从指定库中import ToolComponent, ToolComponentConfig, RestfulApi, Param
# - tool_config = ToolComponentConfig() 为默认格式，按照此格式生成即可
# - 必须定义RestfulApi对象，并绑定到ToolComponent中。用户会提供如下格式的工具信息：
"""
{
    "id": "weather_api",
    "name": "WeatherQuery",
    "description": "天气查询接口",
    "category": "天气",
    "method": "GET",
    "path": "http://127.0.0.1:9000/mock_weather",
    "headers": {"Content-Type": "application/json"},
    "params": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "城市名称，支持中文城市名"
            },
            "date": {
                "type": "string",
                "description": "日期，格式不限"
            }
        },
        "required": ["location"]
    },
    "response": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称（拼音形式）"
            },
            "weather": {
                "type": "string",
                "description": "天气描述（固定为\"小雨\"）"
            },
            "temperature": {
                "type": "number",
                "description": "当前温度（固定为29.92）"
            }
        }
    }
}
"""
# - 在生成RestfulApi对象时，name、description、params、path、method根据用户提供的工具信息生成，headers和response固定为空，无需修改

# 7. CodeComponent 示例
class CustomCodeComponent(WorkflowComponent, ComponentExecutable):
    def __init__(self, node_id):
        super().__init__()
        self.node_id = node_id

    async def invoke(self, inputs: Input, runtime: Runtime, context: Context) -> Output:
        num = inputs["num"]
        if num > 0:
            return {"result": num}
        return {"result": 0}

def create_custom_code_component() -> CustomCodeComponent:
    """创建代码组件"""
    return CustomCodeComponent(node_id="code")

# **重要说明**：
# - 创建CodeComponent组件时，需要先自定义一个类，继承自WorkflowComponent和ComponentExecutable，并实现invoke方法
# - 自定义的类需要实现invoke方法，invoke方法的入参固定为inputs、runtime和context，inputs为组件的输入，runtime为组件的运行时，context为组件的上下文
# - invoke方法的返回值为组件的输出，输出为字典类型，字典的键为组件的输出变量名，值为组件的输出变量值
# - 代码组件的代码逻辑在invoke方法中编写，代码逻辑需要根据组件的输入和运行时进行处理，并返回组件的输出
# - 在类定义完成后，使用create_custom_code_component函数创建组件实例
# - 不同的代码组件需要定义不同的类，实现不同的invoke方法

# 8. BranchComponent 示例
def create_branch_component() -> BranchComponent:
    """创建分支组件"""
    return BranchComponent()

# **重要说明**：
# - 创建BranchComponent组件时， 固定采用上述格式，不同分支组件仅函数名称不同
# - 分支节点的具体条件判断及分支设计不在此编写
