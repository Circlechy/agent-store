# openJiuwen WorkflowAgent 框架关键规范（必须严格遵守）

工作流构建包括两个核心步骤：
1. 定义组件：在 components.py 中创建组件创建函数
2. 注册和连接组件：在 workflow_builder.py 中将组件实例化、注册至工作流，然后连接组件

## 一、组件类型

工作流支持以下8种组件类型：
1. **Start**：工作流开始组件，必须包含且仅有一个
2. **End**：工作流结束组件，必须包含且仅有一个
3. **LLMComponent**：大模型组件，用于所有需要 AI 处理的任务（提取、分析、格式化等）
4. **QuestionerComponent**：提问组件，当需要询问用户或提取参数时使用
5. **IntentDetectionComponent**：意图识别组件，识别输入信息的意图，根据意图决定工作流下一步执行哪个组件
6. **ToolComponent**：工具组件，调用真实的外部API完成任务
7. **CodeComponent**：代码组件，通过自定义代码执行任务
8. **BranchComponent**：分支组件，根据条件决定工作流下一步执行哪个组件

## 二、组件定义关键规则

### 1. Start组件（固定格式）

```python
from openjiuwen.core.component.start_comp import Start

def create_start_component():
    """创建开始组件"""
    return Start({"inputs": [{"id": "query", "type": "String", "required": "true", "sourceType": "ref"}]})
```

**重要规则**：
- 创建Start组件时，**必须**采用上述固定格式
- **强制要求**：Start组件的输入变量名**必须为`query`**，禁止使用其他任何值（如`user_input`、`text`、`message`等）
- 在workflow_builder.py中注册Start组件时，`inputs_schema`必须为：`{"query": "${query}"}`

### 2. End组件

```python
from openjiuwen.core.component.end_comp import End

def create_end_component():
    """创建结束组件"""
    return End({"responseTemplate": "{{output}}"})
```

**重要规则**：
- End组件创建时，固定使用形如`{"responseTemplate": "{{output}}"}`的字典
- 字典**有且仅有`responseTemplate`字段**，没有其他字段
- 引用变量时**必须使用双花括号格式**：`{{output}}`，**禁止使用单花括号**：`{output}`

### 3. LLMComponent

```python
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig

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
```

**重要规则**：
- `response_format`：**必须**使用`{"type": "json"}`
- 引用输入变量时**必须使用双花括号格式**：`{{query}}`，**禁止使用单花括号**
- `model`：**必须**使用`create_model_config()`函数创建

### 4. IntentDetectionComponent

**关键限制1：不会输出任何变量**
- IntentDetectionComponent**不会输出任何变量**，它只用于分支判断
- **禁止**其他组件在`inputs_schema`中引用意图识别组件的输出

**关键限制2：禁止使用add_connection**
- IntentDetectionComponent具有分支功能，**禁止**使用`flow.add_connection()`连接后续组件
- **必须**使用`add_branch()`方法添加分支

**关键限制3：分支编号规则**
- `${intent.classification_id} == 0` **固定为默认分支**，必须存在
- 预设意图从1开始编号：`${intent.classification_id} == 1`、`${intent.classification_id} == 2`等

### 5. BranchComponent

**关键限制：禁止使用add_connection**
- BranchComponent具有分支功能，**禁止**使用`flow.add_connection()`连接后续组件
- **必须**使用`add_branch()`方法添加分支

**完整性要求（必须严格遵守）**：
- **必须实现else分支**，确保所有可能的情况都有对应的处理逻辑
- else分支用于处理所有条件分支都不满足的情况，防止工作流执行时出现未覆盖的场景
- else分支通常指向End组件或默认处理组件

**正确示例**：
```python
branch_comp.add_branch("${start.query} < 0", ["end"], "负数分支")
branch_comp.add_branch("${start.query} > 1", ["llm"], "正数分支")
branch_comp.add_branch("True", ["end"], "else分支")  # else分支：处理其他所有情况
```

## 三、工作流注册和连接规则

### 1. 组件注册

**Start组件和End组件（特殊注册方式）**：
```python
flow.set_start_comp(start_comp_id="start", component=start, inputs_schema={"query": "${query}"})
flow.set_end_comp(end_comp_id="end", component=end, inputs_schema={"output": "${plugin.data}"})
```

**其他组件（统一注册方式）**：
```python
flow.add_workflow_comp(comp_id="extract_location", workflow_comp=llm, inputs_schema={"query": "${start.query}"})
```

### 2. 连接规则

**普通组件连接规则**：
- **适用组件**：Start、LLMComponent、QuestionerComponent、ToolComponent、CodeComponent
- **连接方式**：**必须**使用`flow.add_connection()`连接到后续组件

**分支组件连接规则**：
- **适用组件**：BranchComponent、IntentDetectionComponent
- **连接方式**：**禁止**使用`flow.add_connection()`，**必须**使用`add_branch()`方法

### 3. inputs_schema 输入参数值规则

**引用赋值格式**：
- **格式**：`"${source_component.output_var}"`
- **规则**：
  - 引用格式必须严格为`"${source_component.output_var}"`，禁止增加其他内容
  - 每个输入参数只能引用一个输出变量，禁止通过表达式组合多个输出变量

**正确示例**：
```python
inputs_schema={
    "analysis": "${llm_comp1.analysis}", 
    "recommendations": "${llm_comp2.recommendations}"
}
```

**错误示例**：
```python
inputs_schema={"output": "当前回复：${llm_comp.response}"}  # 错误：禁止增加其他内容
inputs_schema={"output": "${llm_comp.response}|${start.query}"}  # 错误：禁止组合多个输出变量
```

## 四、代码结构约束

### 1. import语句约束

**必须全部集中在文件开头**：
- **components.py**：所有import语句必须放在文件最开头
- **workflow_builder.py**：所有import语句必须放在文件最开头，包括：
  - `import setup_path`（必须在导入 openjiuwen 之前）
  - `from config import create_workflow_config, ...`
  - `from components import (所有组件创建函数)`
  - `from openjiuwen.core.workflow.base import Workflow`
- **禁止**在函数内部或组件创建函数附近添加import语句

### 2. 组件注册约束

- 工作流中**只能有一个End组件**，不能有多个End组件
- End组件**只能**使用`set_end_comp`注册，不能使用`add_workflow_comp`注册
- Start组件**只能**使用`set_start_comp`注册，不能使用`add_workflow_comp`注册
- 所有在连接中被引用的组件（除了 start 和 end）都**必须**通过`flow.add_workflow_comp()`注册

### 3. 组件连接约束

- **必须**连接所有组件，不能遗漏任何连接
- LLMComponent、QuestionerComponent、ToolComponent、CodeComponent等组件**必须**通过`flow.add_connection()`连接到后续组件
- IntentDetectionComponent和BranchComponent**禁止**使用`add_connection`，**必须**使用`add_branch`
- End组件是终点，不需要连接其他组件
