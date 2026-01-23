# 工作流修改指南

## 概述

本指南专门用于工作流修改场景，涵盖需求分析、新工作流结构生成和文件修改的完整流程。必须严格遵守 openJiuwen WorkflowAgent 框架规范。

## 核心原则

### 1. 工作流拓扑优先（最重要）
- **必须通过修改工作流拓扑结构来满足需求**，而不是在 component 文件中添加普通函数
- **如果需求是增加新功能，应该添加新的组件节点，然后重新连接拓扑**
- **如果需求是修改现有功能，应该修改对应组件的描述和配置**
- **严禁**在 `components.py` 中添加普通辅助函数（如 `format_recommendations_as_letter`）

### 2. 完整性要求
- `components` 字段是必填的，绝对不能为空数组
- `components` 必须包含至少 Start 和 End 组件，以及所有必要的中间组件（包括保留的和新增的）
- `workflow_structure` 必须包含完整的拓扑连接（start/edges/end）
- 生成的 `components` 和 `workflow_structure` 必须是完整的新工作流结构

### 3. 框架规范优先
- 所有修改必须符合 openJiuwen WorkflowAgent 框架规范
- 参考 `framework-rules.md` 中的详细规则
- 不能违反框架的任何强制性约束

## 第一部分：需求分析和新结构生成

### 分析流程

#### 步骤 1: 理解所有需求
- 仔细阅读历史需求（初始需求）
- 理解当前修改需求
- 确定整体目标

#### 步骤 2: 分析现有工作流
- 查看 `workflow_builder.py` 了解当前拓扑结构
- 查看 `components.py` 了解现有组件
- 识别需要保留的组件和需要新增/修改的组件

#### 步骤 3: 生成新的工作流结构
- 根据所有需求（历史 + 当前）生成新的组件列表
  - **保留现有组件**：如果现有组件仍然需要，必须在新的 `components` 列表中保留它们
  - **添加新组件**：如果需求要求增加新功能，应该添加新的组件节点
- 生成新的工作流拓扑结构
  - 必须根据新的组件列表重新构建 `workflow_structure`
  - 确保所有组件都正确连接
- 确定需要修改的文件（通常包括 `components.py` 和 `workflow_builder.py`）

### 输出格式（分析阶段）

```json
{
    "files_to_modify": ["components.py", "workflow_builder.py"],
    "modification_plan": {
        "components.py": "添加新的组件创建函数 create_format_as_letter_component",
        "workflow_builder.py": "更新拓扑连接，添加 format_as_letter 组件到流程中"
    },
    "components": [
        {
            "component_id": "start",
            "component_name": "开始组件",
            "component_type": "Start",
            "description": "工作流开始节点"
        },
        {
            "component_id": "generate_recommendations",
            "component_name": "生成推荐歌曲组件",
            "component_type": "LLMComponent",
            "description": "根据用户输入生成推荐歌曲"
        },
        {
            "component_id": "format_as_letter",
            "component_name": "格式化信件组件",
            "component_type": "LLMComponent",
            "description": "将推荐歌曲格式化为友好易读的信件格式"
        },
        {
            "component_id": "end",
            "component_name": "结束组件",
            "component_type": "End",
            "description": "工作流结束节点"
        }
    ],
    "workflow_structure": {
        "start": "start",
        "edges": [
            {"from": "start", "to": "generate_recommendations"},
            {"from": "generate_recommendations", "to": "format_as_letter"},
            {"from": "format_as_letter", "to": "end"}
        ],
        "end": "end"
    }
}
```

### 组件格式要求

每个组件必须包含以下字段：
- **component_id**: 组件ID，使用下划线命名（如 "analyze_preferences"）
  - Start 组件：固定为 "start"
  - End 组件：固定为 "end"
  - 其他组件：使用描述性名称，如 "analyze_text", "generate_summary"
- **component_name**: 组件中文名称，如 "开始组件"、"文本分析组件"
- **component_type**: 组件类型，必须是以下之一：
  - "Start"、"End"、"LLMComponent"、"QuestionerComponent"、"IntentDetectionComponent"、"ToolComponent"、"CodeComponent"、"BranchComponent"
- **description**: 组件功能描述，简洁清晰地描述组件的功能

### 常见修改场景

#### 场景 1: 添加新功能节点
**需求**: 生成推荐歌曲后，将歌曲整理成一封友好易读的信件格式再输出

**分析**:
- 现有流程: start -> generate_recommendations -> end
- 需要添加: format_as_letter 组件（LLMComponent）
- 新流程: start -> generate_recommendations -> format_as_letter -> end

**修改文件**:
- `components.py`: 添加 `create_format_as_letter_component` 函数
- `workflow_builder.py`: 更新拓扑连接

#### 场景 2: 修改现有组件
**需求**: 修改推荐歌曲组件的提示词，使其生成更详细的推荐

**分析**:
- 不需要添加新组件
- 只需要修改 `generate_recommendations` 组件的配置
- 拓扑结构不变

**修改文件**:
- `components.py`: 修改 `create_generate_recommendations_component` 函数

## 第二部分：文件修改指南

### 修改 workflow_builder.py

**关键要求**:
1. 根据新的 `workflow_structure` 重新构建 `build_workflow()` 函数中的拓扑连接（edges）
2. 确保所有组件都已正确注册
3. 确保所有连接都已正确建立

**步骤**:
1. 查看新的 `workflow_structure` 中的 `edges` 列表
2. 根据 `edges` 更新 `flow.add_connection()` 调用
3. 确保所有在 `edges` 中引用的组件都已注册

**示例**:
```python
# 新的 workflow_structure
{
    "start": "start",
    "edges": [
        {"from": "start", "to": "generate_recommendations"},
        {"from": "generate_recommendations", "to": "format_as_letter"},
        {"from": "format_as_letter", "to": "end"}
    ],
    "end": "end"
}

# 修改后的 build_workflow() 函数
def build_workflow():
    flow = Workflow(...)
    
    # 注册所有组件
    start = create_start_component()
    generate_recommendations = create_generate_recommendations_component()
    format_as_letter = create_format_as_letter_component()  # 新增组件
    end = create_end_component()
    
    # 注册组件
    flow.set_start_comp(start_comp_id="start", component=start, inputs_schema={"query": "${query}"})
    flow.add_workflow_comp(comp_id="generate_recommendations", workflow_comp=generate_recommendations, 
                          inputs_schema={"query": "${start.query}"})
    flow.add_workflow_comp(comp_id="format_as_letter", workflow_comp=format_as_letter,  # 新增注册
                          inputs_schema={"recommendations": "${generate_recommendations.recommendations}"})
    flow.set_end_comp(end_comp_id="end", component=end, 
                     inputs_schema={"output": "${format_as_letter.formatted_letter}"})  # 更新输入
    
    # 根据新的 edges 建立连接
    flow.add_connection("start", "generate_recommendations")
    flow.add_connection("generate_recommendations", "format_as_letter")  # 新增连接
    flow.add_connection("format_as_letter", "end")  # 更新连接
    
    return flow
```

### 修改 components.py

**关键要求**:
1. 根据新的 `components` 列表添加或修改组件创建函数
2. **严禁**添加普通辅助函数
3. 所有组件必须符合框架规范

**步骤**:
1. 查看新的 `components` 列表
2. 对于新增的组件，添加对应的 `create_xxx_component()` 函数
3. 对于需要修改的组件，更新对应的组件创建函数

**示例**:
```python
# 新的 components 列表包含 format_as_letter 组件
{
    "component_id": "format_as_letter",
    "component_name": "格式化信件组件",
    "component_type": "LLMComponent",
    "description": "将推荐歌曲格式化为友好易读的信件格式"
}

# 在 components.py 中添加
def create_format_as_letter_component() -> LLMComponent:
    """创建格式化信件组件"""
    system_prompt = "你是一个友好的助手，擅长将信息整理成易读的信件格式。"
    user_prompt = """请将以下推荐歌曲信息整理成一封友好易读的信件格式：

{{recommendations}}

要求：
1. 使用友好的语气
2. 格式清晰易读
3. 包含完整的歌曲信息"""
    
    config = LLMCompConfig(
        model=create_model_config(),
        template_content=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json"},
        output_config={
            "formatted_letter": {"type": "string", "description": "格式化后的信件内容", "required": True}
        },
    )
    return LLMComponent(config)
```

**错误示例**（禁止）:
```python
# ❌ 错误：添加普通函数
def format_recommendations_as_letter(recommendations):
    """将推荐歌曲信息格式化为友好信件格式"""
    # ... 普通函数实现
    return letter
```

## 修改检查清单

### workflow_builder.py 检查
- [ ] 所有在 `workflow_structure.edges` 中引用的组件都已注册
- [ ] 所有连接都已根据新的 `edges` 更新
- [ ] Start 组件的 `inputs_schema` 使用 `{"query": "${query}"}`
- [ ] End 组件的 `inputs_schema` 正确引用最后一个组件的输出
- [ ] 所有组件的 `inputs_schema` 正确引用上游组件的输出变量

### components.py 检查
- [ ] 所有在 `components` 列表中的组件都有对应的创建函数
- [ ] 没有添加普通辅助函数
- [ ] 所有组件创建函数都符合框架规范
- [ ] LLMComponent 的 `response_format` 使用 `{"type": "json"}`
- [ ] 所有模板中的变量引用使用双花括号 `{{variable}}`

## 常见错误和修复

### 错误 1: 在 components.py 中添加普通函数
**问题**: 添加了 `def format_recommendations_as_letter(...)` 这样的普通函数

**修复**: 改为添加 `create_format_as_letter_component()` 函数，返回 LLMComponent 实例

### 错误 2: 没有更新 workflow_builder.py 的拓扑
**问题**: 添加了新组件但没有更新连接关系

**修复**: 根据新的 `workflow_structure.edges` 更新所有连接

### 错误 3: 组件注册不完整
**问题**: 在 `edges` 中引用了组件但没有注册

**修复**: 确保所有在 `edges` 中引用的组件（除了 start 和 end）都通过 `flow.add_workflow_comp()` 注册

### 错误 4: inputs_schema 引用错误
**问题**: 引用了不存在的输出变量或格式错误

**修复**: 确保引用的变量名与组件定义中的 `output_config` 一致，格式为 `"${component_id.output_var}"`

## 注意事项

1. **禁止在 components.py 中添加普通函数**
   - 错误示例: 添加 `def format_recommendations_as_letter(recommendations): ...`
   - 正确做法: 添加 `create_format_as_letter_component()` 函数，返回 LLMComponent 实例

2. **必须通过工作流拓扑来满足需求**
   - 所有功能都应该通过组件节点实现
   - 组件之间的数据传递通过 `inputs_schema` 配置

3. **保持组件类型一致性**
   - 格式化、分析等任务应该使用 LLMComponent
   - 不要使用 CodeComponent 来实现可以通过 LLMComponent 实现的功能

4. **确保拓扑完整性**
   - 所有组件都必须有明确的连接路径
   - 从 start 到 end 必须有一条完整的路径
   - 不能有孤立节点

5. **保留现有组件**
   - 如果现有组件仍然需要，必须在新的 `components` 列表中保留它们
   - 生成的新结构必须是完整的工作流结构，包含所有需要的组件
