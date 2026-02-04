# ReAct Agent Tools 生成规则

## 概述
生成 `tools_analysis.py` 文件，包含工具创建函数。该文件用于定义 ReActAgent 使用的工具。

## 关键要求

### 1. 导入必要的模块
```python
from typing import List
from openjiuwen.core.utils.tool.service_api.restful_api import RestfulApi
from openjiuwen.core.utils.tool.param import Param
```

**注意**：只导入 RestfulApi 相关模块，不需要导入 LocalFunction（除非确实需要本地函数工具）。

### 2. 创建 `get_all_tools()` 函数

函数签名：
```python
def get_all_tools() -> List:
```

该函数应该返回所有工具实例的列表，供 `local_agent.py` 导入使用。

### 3. 工具创建规则

#### 3.1 RestfulApi 工具（主要类型）

所有工具都是 RestfulApi 类型，使用以下方式创建：

```python
tool = RestfulApi(
    name="工具名称",
    description="工具功能描述",
    path="完整的 API URL",
    method="HTTP方法（GET/POST等）",
    headers={"Content-Type": "application/json"},  # 如果存在，否则使用 {}
    params=[
        Param(name="参数名", description="参数描述", type="string", required=True),
        Param(name="参数名2", description="参数描述2", type="number", required=False),
    ],
    response=[]  # 通常为空列表
)
```

**参数说明**：
- `name`: 工具名称（使用 plan.tools 中的 name 字段）
- `description`: 工具描述（使用 plan.tools 中的 description 字段）
- `path`: 完整的 API URL（使用 plan.tools 中的 path 字段）
- `method`: HTTP 方法（使用 plan.tools 中的 method 字段，如 "GET", "POST"）
- `headers`: 请求头（如果 plan.tools 中存在 headers，使用该值；否则使用 `{}`）
- `params`: 参数列表，每个参数使用 `Param` 对象创建
  - `name`: 参数名（使用 plan.tools 中的参数信息）
  - `description`: 参数描述（使用 plan.tools 中的参数描述）
  - `type`: 参数类型（"string", "number", "boolean" 之一）
  - `required`: 是否必需（使用 plan.tools 中的 required 字段）
- `response`: 通常为空列表 `[]`

#### 3.2 Param 类型

`type` 字段必须是以下之一：
- `"string"`: 字符串类型
- `"number"`: 数字类型
- `"boolean"`: 布尔类型

### 4. 完整示例

```python
"""
工具定义文件
"""
from typing import List
from openjiuwen.core.utils.tool.service_api.restful_api import RestfulApi
from openjiuwen.core.utils.tool.param import Param

def get_all_tools() -> List:
    """
    获取所有工具
    
    Returns:
        工具列表，包含所有 RestfulApi 工具实例
    """
    # 工具1：天气查询
    weather_tool = RestfulApi(
        name="WeatherQuery",
        description="查询指定城市的天气信息，包括温度、湿度、风速等",
        path="https://api.openweathermap.org/data/2.5/weather",
        method="GET",
        headers={"Content-Type": "application/json"},
        params=[
            Param(name="city", description="城市名称（英文或中文）", type="string", required=True),
            Param(name="units", description="温度单位（metric: 摄氏度, imperial: 华氏度）", type="string", required=False),
        ],
        response=[],
    )
    
    # 工具2：其他工具...
    # tool2 = RestfulApi(...)
    
    return [weather_tool]  # 返回所有工具的列表
```

### 5. 如果没有工具

如果 `plan.tools` 为空或不需要工具，生成空函数：

```python
from typing import List

def get_all_tools() -> List:
    """
    获取所有工具
    
    Returns:
        工具列表（空列表，表示不使用工具）
    """
    return []
```

## 重要注意事项

- **所有工具都是 RestfulApi 类型**，不要创建 LocalFunction（除非确实需要）
- **必须严格按照 plan.tools 中的信息创建工具**，不要修改或遗漏任何字段
- `path` 字段是完整的 API URL，不要修改
- `method` 字段可能是 "GET" 或 "POST"，必须使用 plan.tools 中的值
- `headers` 字段如果存在，必须使用 plan.tools 中的值；如果不存在，使用空字典 `{}`
- `params` 必须使用 `Param` 对象列表，每个参数的信息必须与 plan.tools 中完全一致
- 函数应该返回所有工具的列表，供 `local_agent.py` 导入使用
- 代码要清晰、模块化，符合高质量代码标准
- 每个函数都要有详细的文档字符串

## 与 local_agent.py 的集成

`local_agent.py` 会从本文件导入工具：

```python
from tools_analysis import get_all_tools

tools = get_all_tools()
if tools:
    agent.add_tools(tools)
```

因此，`get_all_tools()` 函数必须返回工具实例列表，而不是工具配置字典。
