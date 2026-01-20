# ReAct Agent 模式规划 Schema

## 任务
根据用户需求，生成 ReAct Agent 的代码规划。

## 输出格式
严格按以下 JSON 格式输出，不要添加其他内容：

```json
{
    "files": [
        "config.py",
        "tools_analysis.py",
        "local_agent.py",
        "main.py"
    ],
    "key_symbols": [
        "类名或函数名列表"
    ],
    "skills": ["react-agent-skill"],
    "include_references": {},
    "token_budget": 8000,
    "smoke_tests": ["python main.py"],
    "agent_description": "Agent 功能描述",
    "tools": [
        {
            "name": "ToolName",
            "description": "工具功能描述",
            "parameters": {
                "param1": "参数1描述（包括类型和是否必需）",
                "param2": "参数2描述（包括类型和是否必需）"
            }
        }
    ],
    "system_prompt": "Agent 的系统提示词，定义其角色和行为"
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| files | ✅ | 需要生成的文件列表，默认4个文件 |
| key_symbols | ✅ | 关键类名、函数名 |
| agent_description | ✅ | Agent 整体功能描述 |
| tools | ✅ | **必须从可用工具列表中选择**，每个工具包含 name/description/parameters（只包含需求描述，不包含具体实现细节如 path、method 等，这些将在生成阶段根据可用工具列表自动生成）。如果用户需求不需要工具，返回空数组 [] |
| system_prompt | ✅ | Agent 的系统提示词 |
| skills | ✅ | 固定为 ["react-agent-skill"] |
| smoke_tests | ✅ | 测试命令，默认 ["python main.py"] |

## 示例

用户需求：「创建一个天气查询助手」

**注意**：工具名称（name）必须与可用工具列表中的 name 字段完全一致。例如，如果可用工具列表中有 "WeatherQuery"，则必须使用 "WeatherQuery" 而不是 "WeatherTool"。

```json
{
    "files": ["config.py", "tools_analysis.py", "local_agent.py", "main.py"],
    "key_symbols": ["WeatherQuery", "create_agent", "main"],
    "skills": ["react-agent-skill"],
    "include_references": {},
    "token_budget": 8000,
    "smoke_tests": ["python main.py"],
    "agent_description": "天气查询助手：可以查询指定城市的天气信息，支持多城市查询",
    "tools": [
        {
            "name": "WeatherQuery",
            "description": "查询指定城市或坐标位置的实时天气信息，包括温度、湿度、风速等",
            "parameters": {
                "location": "城市名称（string，可选）：支持中文城市名（如\"北京\"、\"上海\"）",
                "lat": "纬度坐标（number，可选）",
                "lon": "经度坐标（number，可选）"
            }
        }
    ],
    "system_prompt": "你是一个天气查询助手。用户询问天气时，使用 WeatherQuery 查询并友好地回复结果。"
}
```
