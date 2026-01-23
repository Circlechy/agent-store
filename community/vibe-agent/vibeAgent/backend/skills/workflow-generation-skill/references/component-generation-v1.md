# Component Generation Reference

## 生成规则

components.py 文件用于创建所有工作流组件。

**关键要求**：
1. **import语句必须全部集中在文件开头**
   - 所有import语句必须放在文件的最开始位置，不要分散在各个组件示例中
   - 必须导入：`import setup_path`（必须在导入 openjiuwen 之前）
   - 必须导入：`from config import create_model_config`
   - 根据实际使用的组件类型，选择需要的导入语句

2. **所有组件创建函数必须有完整的实现**，不能只是函数签名

3. **函数名必须完全匹配**plan 中定义的组件列表，不能遗漏任何函数

## 必需的导入

```python
import setup_path  # 必须在导入 openjiuwen 之前
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from config import create_model_config  # 导入配置函数
```

## 组件创建函数

### Start 组件

```python
def create_start_component() -> Start:
    """创建开始组件"""
    return Start({"inputs": [{"id": "query", "type": "String", "required": "true", "sourceType": "ref"}]})
```

**重要**：
- Start 组件配置 inputs 字段
- inputs 中必须包含 query 字段

### End 组件

```python
def create_end_component() -> End:
    """创建结束组件"""
    return End({"responseTemplate": "{{output}}"})
```

**关键规则**：
1. End 组件**固定**使用 `{"responseTemplate": "{{output}}"}`
2. End 组件**只配置** responseTemplate，**不能**有 inputs 字段
3. responseTemplate 必须使用双花括号格式：`{{output}}`
4. **固定格式**：`End({"responseTemplate": "{{output}}"})`

**错误示例**（禁止使用）：
- `End({"responseTemplate": "${output}"})`  # 错误：使用了单花括号
- `End({"responseTemplate": "{{recommendations}}"})`  # 错误：应该使用固定的 "{{output}}"
- `End({"responseTemplate": "{{output}}", "inputs": [...]})`  # 错误：End 组件不应该有 inputs 字段
- `End({"inputs": [...]})`  # 错误：End 组件不应该有 inputs 字段

**说明**：
- 数据通过 workflow_builder.py 中的 set_end_comp 的 inputs_schema 传递
- 例如：`flow.set_end_comp("end", end, inputs_schema={"output": "${last_component.field}}"})`
- 这里的 "output" 键名是固定的，必须与 End 组件的固定 responseTemplate（`{{output}}`）匹配
- 无论最后一个组件输出什么字段，都映射到 "output" 键名

### LLMComponent

```python
def create_xxx_component() -> LLMComponent:
    """创建 LLM 组件"""
    model_config = create_model_config()
    config = LLMCompConfig(
        model=model_config,
        template_content=[{"role": "user", "content": "处理用户查询：{{query}}"},],
        response_format={"type": "json"},  # 必须使用 {"type": "json"}
        output_config={
            "output_field": {"type": "string", "description": "输出描述", "required": True}
        },
    )
    return LLMComponent(config)
```

**关键规则**：

#### 1. template_content 变量引用规则

**核心规则**：
- template_content 中的变量名（如 `{{analysis}}`）必须与 workflow_builder.py 中 inputs_schema 的键名（如 "analysis"）完全一致
- template_content 中直接使用字段名，**不要**使用 `{{component_id.field}}` 的形式

**正确示例**：
```python
# components.py (generate_recommendations)
template_content=[{"role": "user", "content": "根据分析结果：{{analysis}}生成推荐"}]

# workflow_builder.py
inputs_schema={"analysis": "${analyze_user_input.analysis}"}
```
说明：workflow_builder.py 将 analyze_user_input 组件的 analysis 字段映射到当前组件的 analysis 输入，components.py 的 template_content 中直接使用 `{{analysis}}`，对应 inputs_schema 的键名。

**错误示例**（禁止使用）：
```python
# components.py
template_content=[{"role": "user", "content": "根据分析结果：{{analyze_user_input.analysis}}生成推荐"}]  # 错误：不应该使用组件ID
```
说明：template_content 中的变量应该直接使用字段名，而不是 `{{component_id.field}}` 的形式。

#### 2. response_format 配置

**强制要求**：
- 所有 LLMComponent 的 response_format **必须使用**：`response_format={"type": "json"}`（ -> LLMComponent:
    """创建提取用户偏好组件"""
    model_config = create_model_config()
    config = LLMCompConfig(
        model=model_config,
        template_content=[{
            "role": "user", 
            "content": "请从以下用户输入中提取音乐偏好信息：\n\n用户输入：{{query}}\n\n请提取以下信息：\n1. 音乐类型\n2. 情绪\n3. 场景\n\n请以结构化的方式输出提取的信息。"
        }],
        response_format={"type": "json"},  # 必须使用 {"type": "json"}
        output_config={
            "preferences": {"type": "string", "description": "提取的用户音乐偏好", "required": True}
        },
    )
    return LLMComponent(config)
```

**说明**：
- template_content 中使用 `{{query}}`（从 start.query 获取）
- output_config 定义 "preferences" 字段（供下游组件使用）

### 示例 2：接收上游组件输出

```python
def create_generate_recommendations_component() -> LLMComponent:
    """创建生成推荐组件"""
    model_config = create_model_config()
    config = LLMCompConfig(
        model=model_config,
        template_content=[{
            "role": "user", 
            "content": "基于以下用户偏好信息，生成个性化的音乐推荐：\n\n用户偏好：{{preferences}}\n\n请推荐3-5首符合用户偏好的音乐。"
        }],
        response_format={"type": "json"},  # 必须使用 {"type": "json"}
        output_config={
            "recommendations": {"type": "string", "description": "生成的音乐推荐列表", "required": True}
        },
    )
    return LLMComponent(config)
```

**说明**：
- template_content 中使用 `{{preferences}}`（对应 workflow_builder.py 中 inputs_schema 的键名）
- workflow_builder.py 中应该配置：`inputs_schema={"preferences": "${extract_preferences.preferences}"}`
- output_config 定义 "recommendations" 字段（供下游组件使用）

## 常见错误

### 错误 1：End 组件配置错误

**问题**：End 组件使用了错误的 responseTemplate

**错误代码**：
```python
End({"responseTemplate": "${output}"})  # 错误：使用了单花括号
End({"responseTemplate": "{{recommendations}}"})  # 错误：应该使用固定的 "{{output}}"
End({"responseTemplate": "{{output}}", "inputs": [...]})  # 错误：End 组件不应该有 inputs 字段
```

**解决**：
```python
End({"responseTemplate": "{{output}}"})  # 正确：固定格式
```

### 错误 2：template_content 使用组件ID

**问题**：template_content 中使用了 `{{component_id.field}}` 格式

**错误代码**：
```python
template_content=[{"role": "user", "content": "根据分析结果：{{analyze_user_input.analysis}}生成推荐"}]
```

**解决**：
```python
template_content=[{"role": "user", "content": "根据分析结果：{{analysis}}生成推荐"}]
```

**说明**：template_content 中直接使用字段名，workflow_builder.py 负责映射组件输出到字段名。

### 错误 3：response_format 格式错误

**问题**：使用了 "text" 或 "markdown" 格式

**错误代码**：
```python
response_format={"type": "text"}  # 错误：应该使用 "json"
response_format={"type": "markdown"}  # 错误
```

**解决**：
```python
response_format={"type": "json"}  # 正确：必须使用 {"type": "json"}
```

### 错误 4：output_config 字段名不一致

**问题**：output_config 中定义的字段名与 workflow_builder.py 中使用的字段名不一致

**错误代码**：
```python
# components.py
output_config={"preferences": {...}}

# workflow_builder.py
inputs_schema={"user_preferences": "${extract_preferences.preferences}"}  # 错误：键名不一致
```

**解决**：
```python
# components.py
output_config={"preferences": {...}}

# workflow_builder.py
inputs_schema={"preferences": "${extract_preferences.preferences}"}  # 正确：键名一致
```

### QuestionerComponent

**重要**：QuestionerComponent 有两种工作模式，由 `question_content` 控制。

#### 模式 1：智能提取模式（question_content=""）

**用途**：从用户输入中智能提取变量

**工作方式**：
- 如果用户输入中已经包含所需变量的信息，直接执行提取操作，不会向用户提问
- 如果用户输入中没有包含所需变量的信息，向用户提问，再从用户回复中提取变量

**适用场景**：需要从用户输入中提取参数的工作流（如温度调节、地点查询等）

**示例**：
```python
def create_questioner_component() -> QuestionerComponent:
    """创建提问组件（智能提取模式）"""
    from openjiuwen.core.component.questioner_comp import QuestionerComponent, QuestionerConfig, FieldInfo
    
    key_fields = [
        FieldInfo(field_name="temperature", description="目标温度", required=True),
        FieldInfo(field_name="location", description="地点", required=True),
    ]
    config = QuestionerConfig(
        model=create_model_config(),
        question_content="",  # 空字符串，智能提取模式
        extract_fields_from_response=True,
        field_names=key_fields,
        with_chat_history=False,
    )
    return QuestionerComponent(config)
```

**说明**：`question_content=""` 表示智能提取模式，根据用户输入自动决定是否提问。

#### 模式 2：调查模式（question_content不为空）

**用途**：主动向用户提问进行调查

**工作方式**：
- 不管用户输入中有没有包含变量信息，都必然触发提问
- 提问器会询问用户问题，然后从用户回复中提取变量

**适用场景**：问卷调查、信息收集等工作流

**示例**：
```python
def create_questioner_component() -> QuestionerComponent:
    """创建提问组件（调查模式）"""
    from openjiuwen.core.component.questioner_comp import QuestionerComponent, QuestionerConfig, FieldInfo
    
    key_fields = [
        FieldInfo(field_name="favorite_color", description="最喜欢的颜色", required=True),
    ]
    config = QuestionerConfig(
        model=create_model_config(),
        question_content="请回答以下问题：您最喜欢的颜色是什么？",  # 非空，调查模式
        extract_fields_from_response=True,
        field_names=key_fields,
        with_chat_history=False,
    )
    return QuestionerComponent(config)
```

**说明**：`question_content` 不为空时，表示调查模式，总是会触发提问。

**选择原则**：
- 如果工作流需要从用户输入中智能提取参数（如温度、地点、日期等），使用模式1（question_content=""）
- 如果工作流需要主动向用户提问进行调查（如问卷调查、信息收集等），使用模式2（question_content="具体问题内容"）

### IntentDetectionComponent

```python
def create_intent_detection_component() -> IntentDetectionComponent:
    """创建意图识别组件"""
    from openjiuwen.core.component.intent_detection_comp import IntentDetectionComponent, IntentDetectionCompConfig
    
    config = IntentDetectionCompConfig(
        user_prompt="请判断用户意图",
        category_name_list=["查询某地天气", "创作诗歌"],
        model=create_model_config(),
    )
    return IntentDetectionComponent(config)
```

**重要说明**：
- `user_prompt` 用于提示大模型更好地识别用户意图
- `category_name_list` 为意图分类列表，除列表中的内容外，会默认添加一个默认分类
- `inputs_schema` 必须只包含 `query` 字段（在 workflow_builder.py 中配置）
- **不会输出任何变量**（在 workflow_builder.py 中不能引用其输出）

### ToolComponent

```python
def create_tool_component() -> ToolComponent:
    """创建工具组件"""
    from openjiuwen.core.component.tool_comp import ToolComponent, ToolComponentConfig
    from openjiuwen.core.utils.tool.service_api.restful_api import RestfulApi
    from openjiuwen.core.utils.tool.param import Param
    
    tool_config = ToolComponentConfig()
    
    # 定义 RESTful API 工具
    weather_tool = RestfulApi(
        name="WeatherQuery",
        description="天气查询接口",
        params=[
            Param(name="location", description="城市名称", type="string", required=True),
            Param(name="date", description="日期", type="string", required=True),
        ],
        path="http://127.0.0.1:9000/mock_weather",
        headers={},
        method="GET",
        response=[],
    )
    
    return ToolComponent(tool_config).bind_tool(weather_tool)
```

**重要说明**：
- `tool_config = ToolComponentConfig()` 为默认格式
- `name`、`description`、`params`、`path`、`method` 根据实际工具信息生成
- `headers` 和 `response` 固定为空列表 `[]`
- 输出变量固定为 `data`（字典类型），在 workflow_builder.py 中使用 `${tool_component.data}` 引用

### CodeComponent

```python
from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.runtime.base import ComponentExecutable, Input, Output
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.context_engine.base import Context

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
```

**重要说明**：
- 需要先自定义一个类，继承自 `WorkflowComponent` 和 `ComponentExecutable`
- 实现 `invoke` 方法，入参固定为 `inputs`、`runtime`、`context`
- 返回值为字典类型，字典的键为组件的输出变量名
- 输出变量固定为 `data`（字典类型），在 workflow_builder.py 中使用 `${code_component.data}` 引用

### BranchComponent

```python
def create_branch_component() -> BranchComponent:
    """创建分支组件"""
    from openjiuwen.core.component.branch_comp import BranchComponent
    return BranchComponent()
```

**重要说明**：
- 分支节点的具体条件判断及分支设计在 workflow_builder.py 中使用 `add_branch()` 配置
- 不同分支组件仅函数名称不同

## 最佳实践

1. **使用描述性的函数名**：`create_extract_preferences_component()` 比 `create_llm1_component()` 更清晰
2. **添加详细的文档字符串**：每个函数都应该有清晰的说明
3. **保持代码简洁**：每个组件只负责一个明确的任务
4. **统一命名风格**：函数名使用下划线命名（如 `create_extract_preferences_component`）
5. **import 语句集中**：所有 import 语句必须放在文件开头