# Workflow Builder Generation Reference

## 生成规则

workflow_builder.py 文件用于组装和连接工作流组件。

**必须包含的函数**：
1. `build_workflow()` - 核心函数，组装和连接工作流组件
2. `create_workflow_schema()` - 创建工作流 Schema
3. `build_workflow_agent()` - 构建 WorkflowAgent 实例

## 必需的导入

```python
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata
from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from config import create_workflow_config, WORKFLOW_ID, WORKFLOW_NAME, WORKFLOW_VERSION, WORKFLOW_DESCRIPTION, AGENT_ID, AGENT_VERSION, AGENT_DESCRIPTION
from components import (
    create_start_component,
    create_end_component,
    create_xxx_component,  # 其他组件函数
)
```

## build_workflow() 函数

### 1. 创建 Workflow 实例

```python
flow = Workflow(workflow_config=create_workflow_config())
```

### 2. 实例化所有组件

根据从 `components.py` 中导入的组件创建函数，实例化所有组件。

```python
start = create_start_component()
extract_preferences = create_extract_preferences_component()
generate_recommendations = create_generate_recommendations_component()
end = create_end_component()
```

**重要**：必须实例化 `components.py` 中定义的所有组件函数。

### 3. 注册组件到工作流

**可用组件类型**：

- Start: 工作流开始组件
- End: 工作流结束组件
- LLMComponent: 大模型组件
- QuestionerComponent: 提问组件
- IntentDetectionComponent: 意图识别组件
- ToolComponent: 工具组件
- CodeComponent: 代码组件
- BranchComponent: 分支组件

#### 3.1 注册方式

**Start 组件和 End 组件（特殊注册方式）**：

```python
flow.set_start_comp(start_comp_id="start", component=start, inputs_schema={"query": "${query}"})
flow.set_end_comp(end_comp_id="end", component=end, inputs_schema={"output": "${plugin.data}"})
```

**其他组件（统一注册方式）**：

```python
flow.add_workflow_comp(comp_id="extract_location", workflow_comp=llm, inputs_schema={"query": "${start.query}"})
```

#### 3.2 注册参数说明

- `start_comp_id`、`end_comp_id`、`comp_id`：节点的唯一标识，必须唯一，不能重复
- `component`、`workflow_comp`：组件实例，必须为组件创建函数返回的组件实例
- `inputs_schema`：组件的输入参数，必须为字典类型，键为输入参数名称，值为输入参数值
  - 可以包含多个输入参数，也可以为空字典（无输入参数）

#### 3.3 inputs_schema 输入参数名称规则（必须严格遵守）

各组件类型的输入参数名称必须与 `components.py` 中对应组件创建函数的定义保持一致：

- **Start 组件**：
  - **入参名必须为 `query`**，禁止使用其他任何值（如 `user_input`、`text`、`message` 等）
  - 这是强制要求，必须严格遵守

- **LLMComponent**：
  - 入参名必须与 `template_content` 中 `content` 引用的变量名一致
  - 示例：`template_content=[{"role": "user", "content": "处理用户查询：{{query}}, 日期：{{date}}"}]`
  - 则入参名必须为：`query` 和 `date`

- **ToolComponent**：
  - 入参名必须与 `RestfulApi` 的 `Params` 中定义的输入参数名称一致
  - 示例：`params=[Param(name="location", ...), Param(name="date", ...)]`
  - 则入参名必须为：`location` 和 `date`

- **CodeComponent**：
  - 入参名必须与 `invoke` 函数中 `inputs` 参数的键名一致
  - 示例：`def invoke(self, inputs: Input, ...)` 中 `inputs` 包含 `{"num": 1, "text": "hello"}`
  - 则入参名必须为：`num` 和 `text`

- **End 组件**：
  - 入参名必须与 `responseTemplate` 中引用的变量名一致
  - 示例：`responseTemplate="{{output}}"`
  - 则入参名必须为：`output`

- **IntentDetectionComponent**：
  - **入参只有一个，且必须为 `query`**
  - 禁止包含其他输入参数

- **QuestionerComponent**：
  - 入参中**可根据需求确定字段名称，但必须包含 `query` 字段**

- **BranchComponent**：
  - 当组件是 BranchComponent 时，禁止为其设置 `inputs_schema`
  - 正确示例：`flow.add_workflow_comp("branch_comp", branch_comp)`

#### 3.4 inputs_schema 输入参数值规则

输入参数值有两种赋值方式：

**1. 直接赋值**

- **格式**：`"value"`（字符串格式）
- **说明**：直接将字符串值赋给组件的输入参数
- **示例**：`inputs_schema={"temperature": "25"}`

**2. 引用赋值**

- **格式**：`"${source_component.output_var}"`
- **说明**：引用其他组件的输出变量
- **规则**：
  - 引用格式必须严格为 `"${source_component.output_var}"`，禁止增加其他内容
  - 每个输入参数只能引用一个输出变量，禁止通过表达式组合多个输出变量
  - 输出变量名必须为 `components.py` 中组件创建函数已定义的输出变量名

**各组件类型的输出变量定义**：

- **LLMComponent**：输出变量定义在 `output_config` 中
- **QuestionerComponent**：输出变量定义在 `field_names` 中
- **ToolComponent**：输出变量固定为 `data`（字典类型）
  - 可通过 `${tool_comp.data.key}` 进一步获取字典中的指定键值
  - 具体内容需在工具详情中确认
- **CodeComponent**：输出变量固定为 `data`（字典类型）
  - 可通过 `${code_comp.key}` 进一步获取字典中的指定键值
  - 具体内容由 `invoke` 函数的输出确定

**引用赋值示例**：

- **正确示例**：
```python
inputs_schema={
    "analysis": "${llm_comp1.analysis}", 
    "recommendations": "${llm_comp2.recommendations}"
}
```
说明：两个输入变量分别只引用了一个输出变量

- **错误示例 1**：引用格式包含额外内容
```python
inputs_schema={"output": "当前回复：${llm_comp.response}"}  # 错误：禁止增加其他内容
```

- **错误示例 2**：通过表达式组合多个输出变量
```python
inputs_schema={"output": "${llm_comp.response}|${start.query}"}  # 错误：禁止组合多个输出变量
```


### 4. 连接组件之间的拓扑关系

工作流组件连接有两种方式：

- **add_connection()**：用于普通组件的线性连接
```python
flow.add_connection("source_component_id", "target_component_id")
```

- **add_branch()**：用于意图识别组件和分支组件的条件分支连接
```python
component.add_branch("expression_str", target_list, "branch_id")
```

#### 4.1 普通组件连接（使用 add_connection）

- **适用组件**：Start、LLMComponent、QuestionerComponent、ToolComponent、CodeComponent
- **连接方式**：**必须**使用 `flow.add_connection()` 连接到后续组件
- **示例**：
```python
flow.add_connection("start", "extract_preferences")
flow.add_connection("extract_preferences", "generate_recommendations")
flow.add_connection("generate_recommendations", "end")
```

**重要**：

- **普通组件必须使用 `add_connection()` 连接**，不能使用 `add_branch()`
- End 组件作为工作流终点，不需要连接任何组件

#### 4.2 分支连接规则

- **适用组件**：BranchComponent、IntentDetectionComponent
- **连接方式**：**禁止**使用 `flow.add_connection()`，**必须**使用 `add_branch()` 方法
- **add_branch() 方法参数说明**：
  - `expression_str`：条件表达式，必须为字符串类型
  - `target`：目标组件ID，必须为字符串列表且只能有一个元素
    - 正确：`["end"]`（使用引号）
    - 错误：`[end]`（会被解析为变量）
  - `branch_id`：分支ID，必须为字符串类型
    - 正确：`"pos_branch"`（使用引号）
    - 错误：`pos_branch`（会被解析为变量）
- **错误示例**：
```python
flow.add_connection("branch_comp", "next_comp")  # 错误：分支组件不能使用 add_connection
```

#### 4.3 IntentDetectionComponent 关键规则

- **分支表达式格式**：固定使用 `${intent.classification_id}` 进行判断，其中 `intent` 是注册时的名称
```python
intent.add_branch("${intent.classification_id} == 0", ["end"], "默认分支")
intent.add_branch("${intent.classification_id} == 1", ["llm"], "查询天气分支")
```

- **分支编号规则**：
  - `${intent.classification_id} == 0` **固定为默认分支**，必须存在
  - 预设意图从 1 开始编号：`${intent.classification_id} == 1`、`${intent.classification_id} == 2` 等，依次递增

- **运算符限制**：**只能使用 `==` 运算符**，禁止使用 `!=`、`>`、`<` 等其他运算符

- **输出变量规则**：**不会输出任何变量**，禁止其他组件在 `inputs_schema` 中引用其输出
  - 禁止引用：`${intent.intent}`、`${intent.classification_id}` 等
  - `classification_id` 仅在 `add_branch` 的表达式内部使用，不能作为输出变量被其他组件引用

**错误示例**：

- **错误示例 1**：默认分支编号错误
```python
intent.add_branch("${intent.classification_id} == 0", ["llm"], "创作诗歌")
intent.add_branch("${intent.classification_id} == 1", ["end"], "默认分支")  # 错误：默认分支应该是 0
```

- **错误示例 2**：使用 add_connection 连接
```python
flow.add_connection("intent", "next_comp")  # 错误：必须使用 add_branch
```

- **错误示例 3**：引用意图识别组件的输出
```python
inputs_schema={"intent": "${intent.classification_id}"}  # 错误：意图识别组件没有输出变量
```

- **错误示例 4**：使用非 == 运算符
```python
intent.add_branch("${intent.classification_id} != 0", ["end"], "非默认分支")  # 错误：只能使用 ==
```

#### 4.4 BranchComponent 关键规则

- **分支表达式格式**：灵活自定义
  - 可以直接通过 `${source_component.output_var}` 引用其他组件的输出
  - BranchComponent 注册时不会定义 `inputs_schema`，所以表达式中不能尝试引用自身的变量
  - 表达式必须符合 Python 语法
  - 可以使用各种运算符：`==`、`!=`、`>`、`<`、`>=`、`<=`、`in`、`not in` 等

- **完整性要求**（必须严格遵守）：
  - **必须实现 else 分支**，确保所有可能的情况都有对应的处理逻辑
  - else 分支用于处理所有条件分支都不满足的情况，防止工作流执行时出现未覆盖的场景
  - else 分支通常指向 End 组件或默认处理组件
  - else 分支使用 `"True"` 作为表达式

- **循环功能**：可以通过设置 `target` 参数指向已执行的组件，实现循环功能

**正确示例**（包含 else 分支）：

```python
branch_comp.add_branch("${start.query} < 0", ["end"], "负数分支")
branch_comp.add_branch("${start.query} > 1", ["llm"], "正数分支")
branch_comp.add_branch("True", ["end"], "else分支")  # else 分支：处理其他所有情况
```

**错误示例**：

- **错误示例 1**：缺少 else 分支
```python
branch_by_platform.add_branch("'小红书' in ${start.query}", ["generate_xiaohongshu_content"], "小红书分支")
branch_by_platform.add_branch("'微博' in ${start.query}", ["generate_weibo_content"], "微博分支")
# 错误：缺少 else 分支，当 query 中不包含任何平台名称时，工作流无法继续执行
```

- **错误示例 2**：使用 add_connection
```python
flow.add_connection("branch_comp", "next_comp")  # 错误：必须使用 add_branch
```

- **错误示例 3**：BranchComponent 注册时，禁止出现 inputs_schema；禁止引用自身变量
```python
flow.add_workflow_comp("branch_logic", branch_logic, inputs_schema={"temperature": "${analyze_weather.temperature}"})
branch_logic.add_branch("${branch_logic.temperature} < 10", ["comp_next"], "branch_name")
```

## create_workflow_schema() 函数

```python
def create_workflow_schema() -> WorkflowSchema:
    """创建工作流 Schema"""
    return WorkflowSchema(
        id=WORKFLOW_ID,
        name=WORKFLOW_NAME,
        description=WORKFLOW_DESCRIPTION,
        version=WORKFLOW_VERSION,
        inputs={
            "query": {"type": "string"}
        }
    )
```

**重要**：

- 必须从 `config` 导入 `WORKFLOW_ID`、`WORKFLOW_NAME`、`WORKFLOW_VERSION`、`WORKFLOW_DESCRIPTION`
- `inputs` 只需要定义 `query`

## build_workflow_agent() 函数

```python
def build_workflow_agent() -> WorkflowAgent:
    """构建 WorkflowAgent 实例"""
    # 1. 构建工作流
    flow = build_workflow()
    
    # 2. 创建工作流 Schema
    schema = create_workflow_schema()
    
    # 3. 创建 WorkflowAgentConfig
    workflow_agent_config = WorkflowAgentConfig(
        id=AGENT_ID,  # 使用 id，不是 agent_id
        version=AGENT_VERSION,
        description=AGENT_DESCRIPTION,
        workflows=[schema]  # 使用 workflows 列表，不是 workflow_schema
    )
    
    # 4. 创建 Agent 实例
    workflow_agent = WorkflowAgent(workflow_agent_config)
    
    # 5. 绑定工作流到 Agent
    workflow_agent.bind_workflows([flow])
    
    return workflow_agent
```

**重要**：

- `WorkflowAgentConfig` 的参数是 `id`，不是 `agent_id`
- `WorkflowAgentConfig` 的参数是 `workflows`（列表），不是 `workflow_schema`
- 必须先创建 `WorkflowAgent` 实例，然后调用 `bind_workflows()` 绑定工作流

## 代码生成要求

1. 必须从 `components` 导入所有组件创建函数，函数名必须与 `components.py` 中定义的完全一致
2. 必须调用 `components` 中的所有创建函数，不能遗漏任何组件
3. 必须注册所有组件到工作流，不能遗漏任何组件
4. 必须连接所有组件，不能遗漏任何连接
5. 必须返回构建好的工作流对象
6. **重要**：import 语句必须全部集中在文件开头

## 重要要求（必须严格遵守）

1. **必须严格按照上面的函数列表从 components 导入（不能多也不能少，不能添加列表中没有的函数）**
2. 必须在 `build_workflow()` 中调用所有已导入的组件创建函数（不能遗漏任何组件）
3. **关键**：必须注册所有组件到工作流（不能遗漏任何组件）
   - 所有在连接中被引用的组件（除了 start 和 end）都必须通过 `flow.add_workflow_comp()` 注册
   - 即使组件在 `set_end_comp` 的 `inputs_schema` 中被引用，也必须先注册
   - **错误示例**：只实例化组件，但在连接中引用时没有注册，会导致错误 "Component ID mismatch: nodes [...] are referenced in edges but not registered"
   - **正确示例**：先注册所有组件，然后再连接它们
4. 必须连接所有组件（不能遗漏任何连接）
5. 不要导入 `components.py` 中不存在的函数（这会导致 ImportError）
6. 代码要清晰、模块化，符合高质量代码标准
7. 每个函数都要有详细的文档字符串
8. 正确处理可选输入字段（使用默认值，`required=False`）

## 工作流连接逻辑（根据用户输入和工作流描述）

- 根据工作流描述连接工作流组件，确保所有组件都正确连接，不能遗漏任何组件
- **重要**：流程要尽可能简单，使用线性连接（Start → 组件1 → 组件2 → ... → End）
- 按照描述中的流程顺序连接所有组件
- 确保所有组件都正确连接，不能遗漏任何组件

## 输出格式

请直接输出完整的 Python 代码，不要包含 markdown 代码块标记，确保包含所有必要的导入和组件调用。
