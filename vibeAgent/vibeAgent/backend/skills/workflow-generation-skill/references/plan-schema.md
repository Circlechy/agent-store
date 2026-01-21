# Workflow 模式规划 Schema

## 任务
根据用户需求，生成工作流的规划方案，重点包括工作流的组件信息（`components`）和连接逻辑（`workflow_structure`）。

**重要提示（必须严格遵守）**：
- **components 字段是必填的，绝对不能为空数组 `[]` 或缺失**
- **components 必须包含至少 Start 和 End 组件，以及必要的中间组件**
- **每个组件必须包含以下字段：component_id、component_name、component_type、description**
- **如果 components 为空或缺失，将导致后续代码生成失败**

## 组件类型说明
1. **Start**: 工作流开始组件，**必须有且仅有一个开始组件**
2. **End**: 工作流结束组件，**必须有且仅有一个结束组件**
3. **LLMComponent**: 大模型组件，用于所有需要 AI 处理的任务（分析、格式化等）
4. **QuestionerComponent**: 提问组件，当需要询问用户或者提取参数时使用
   - 用途：QuestionerComponent有两种工作模式：
    - **模式1：智能提取模式**
        * 作用：从用户输入中智能提取变量。如果用户输入中已包含所需变量信息，直接提取不提问；如果没有，则提问后再提取
        * 适用场景：需要从用户输入中提取参数的工作流（如温度调节、地点查询等）
    - **模式2：调查模式**
        * 作用：作为调查功能，主动向用户提问
        * 适用场景：问卷调查、信息收集等工作流
5. **IntentDetectionComponent**: 意图识别组件，识别输入信息的意图，根据意图决定工作流下一步执行哪个组件
6. **ToolComponent**: 工具组件，调用真实的外部API完成任务（**谨慎使用，优先使用 LLMComponent**）
7. **CodeComponent**: 代码组件，通过自定义代码执行任务
8. **BranchComponent**: 分支组件，根据条件决定工作流下一步执行哪个组件

## 组件选择原则（必须严格遵守）
1. **流程尽可能简单**：
   - 尽量减少组件数量，能合并的功能尽量合并到一个组件中

2. **优先使用 LLMComponent**：
   - 从 query 中提取和分析信息使用 LLMComponent
   - 分析和处理数据使用 LLMComponent
   - 格式化输出使用 LLMComponent

3. **避免不必要的组件**：
   - 如果不需要意图识别，不要使用 IntentDetectionComponent
   - IntentDetectionComponent本身具有分支功能，不需要额外配合分支组件使用
   - **QuestionerComponent使用场景**：
     * 当需要从用户输入中智能提取参数（如温度、地点、日期等）时，使用QuestionerComponent（模式1）
     * 当需要主动向用户提问进行调查（如问卷调查、信息收集等）时，使用QuestionerComponent（模式2）
     * 如果可以从 query 中直接提取信息且不需要用户交互，优先使用LLMComponent，不要使用 QuestionerComponent
   - **谨慎使用 ToolComponent**：如果功能可以通过 LLMComponent 实现，优先使用 LLMComponent，而不是 ToolComponent；除非用户明确要求调用真实的外部API，且有合适的工具可用，否则不要生成 ToolComponent

4. 当存在意图识别组件或者分支组件时，必然存在多分支的情况，而多分支必然会有汇合点，在汇合时有以下注意事项：
   - 只有LLMComponent、CodeComponent和End组件可以作为汇合点，其他如QuestionerComponent、ToolComponent不能作为汇合点。

5. **严禁生成多个End组件**：
   - 必须确保只有一个 End 组件

## 组件格式要求
每个组件必须包含以下字段：

- **component_id**: 组件ID，必须使用下划线命名（如 "analyze_preferences"，不能使用 "analyze-preferences" 或 "analyzePreferences"）
  - Start 组件：固定为 "start"
  - End 组件：固定为 "end"
  - 其他组件：使用描述性名称，如 "analyze_text", "generate_summary"

- **component_name**: 组件中文名称，如 "开始组件"、"文本分析组件"、"结束组件"

- **component_type**: 组件类型，必须是以下之一：
  - "Start"
  - "End"
  - "LLMComponent"
  - "QuestionerComponent"
  - "IntentDetectionComponent"
  - "ToolComponent"
  - "CodeComponent"
  - "BranchComponent"

- **description**: 组件功能描述，简洁清晰地描述组件的功能

## 组件格式示例

### 1. Start 组件（必须严格参考）

```json
{
    "component_id": "start",
    "component_name": "开始组件",
    "component_type": "Start",
    "description": "工作流开始节点"
}
```

### 2. LLMComponent 组件

```json
{
    "component_id": "analyze_preferences",
    "component_name": "用户偏好分析组件",
    "component_type": "LLMComponent",
    "description": "分析用户的音乐偏好信息"
}
```

### 3. End 组件（必须严格参考）

```json
{
    "component_id": "end",
    "component_name": "结束组件",
    "component_type": "End",
    "description": "工作流结束节点"
}
```

**注意**：在规划阶段，components 中的每个组件只需要包含上述 4 个字段（component_id, component_name, component_type, description）。

## 生成 工作流组件 的步骤指导

在生成 工作流组件 时，请按照以下步骤思考：

### 步骤 1：分析用户需求
- 理解用户想要实现什么功能
- 确定主要处理步骤

### 步骤 2：确定工作流流程
- **必须包含**：Start（入口）和 End（出口）

### 步骤 3：设计组件列表
- 始终从 Start 组件开始
- 添加必要的中间组件
- 始终以 End 组件结束

### 步骤 4：命名组件
- component_id 使用下划线命名，简洁描述功能
- component_name 使用中文，清晰描述组件用途
- description 简要说明组件功能

### 步骤 5：构建 workflow_structure
- start: 固定为 "start"
- end: 固定为 "end"
- edges: 按照组件顺序连接，确保 Start -> ... -> End 的完整路径

## 输出格式
严格按以下 JSON 格式输出，不要添加其他内容：

```json
{
    "files": [
        "config.py",
        "components.py", 
        "workflow_builder.py",
        "main.py"
    ],
    "key_symbols": [
        "类名或函数名列表"
    ],
    "skills": ["workflow-generation-skill"],
    "include_references": {},
    "token_budget": 8000,
    "smoke_tests": ["python main.py"],
    "workflow_description": "工作流整体功能描述",
    "components": [
        {
            "component_id": "component_id_name",
            "component_name": "组件中文名称",
            "component_type": "Start|End|LLMComponent|QuestionerComponent|IntentDetectionComponent|ToolComponent|CodeComponent|BranchComponent",
            "description": "组件功能描述"
        }
    ],
    "workflow_structure": {
        "start": "起始组件名",
        "edges": [
            {"from": "start", "to": "Component1"},
            {"from": "Component1", "to": "Component2"},
            {"from": "Component2", "to": "end"}
        ],
        "end": "end"
    }
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| files | ✅ | 需要生成的文件列表，默认4个文件 |
| key_symbols | ✅ | 关键类名、函数名 |
| workflow_description | ✅ | 工作流整体描述 |
| components | ✅ | 组件列表，每个组件包含 component_id/component_name/component_type/description（**必填字段，绝对不能为空数组**） |
| workflow_structure | ✅ | 工作流结构，包含 start/edges/end |
| skills | ✅ | 固定为 ["workflow-generation-skill"] |
| smoke_tests | ✅ | 测试命令，默认 ["python main.py"] |

## 示例

用户需求：「创建一个文本摘要工作流」

```json
{
    "files": ["config.py", "components.py", "workflow_builder.py", "main.py"],
    "key_symbols": ["create_start_component", "create_analyze_text_component", "create_generate_summary_component", "create_end_component", "build_workflow"],
    "skills": ["workflow-generation-skill"],
    "include_references": {},
    "token_budget": 8000,
    "smoke_tests": ["python main.py"],
    "workflow_description": "文本摘要工作流：接收文本输入，调用 LLM 生成摘要，返回结果",
    "components": [
        {
            "component_id": "start",
            "component_name": "开始组件",
            "component_type": "Start",
            "description": "工作流开始节点"
        },
        {
            "component_id": "analyze_text",
            "component_name": "文本分析组件",
            "component_type": "LLMComponent",
            "description": "分析用户输入的文本内容"
        },
        {
            "component_id": "generate_summary",
            "component_name": "摘要生成组件",
            "component_type": "LLMComponent",
            "description": "调用 LLM 生成文本摘要"
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
            {"from": "start", "to": "analyze_text"},
            {"from": "analyze_text", "to": "generate_summary"},
            {"from": "generate_summary", "to": "end"}
        ],
        "end": "end"
    }
}
```
