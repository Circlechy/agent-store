# Multi-Agent 模式规划 Schema

## 任务
根据用户需求，生成 Multi-Agent 多智能体系统的代码规划。

## 输出格式
严格按以下 JSON 格式输出，不要添加其他内容：

```json
{
    "files": [
        "config.py",
        "leader_agent.py",
        "worker_agents.py",
        "main.py"
    ],
    "key_symbols": [
        "类名或函数名列表"
    ],
    "skills": ["multi-agent-skill"],
    "include_references": {},
    "token_budget": 8000,
    "smoke_tests": ["python main.py --test \"测试查询\""],
    "leader_description": "Leader Agent 功能描述",
    "worker_descriptions": [
        "Worker1 功能描述",
        "Worker2 功能描述"
    ],
    "coordination_strategy": "协调策略描述"
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| files | ✅ | 需要生成的文件列表，默认4个文件 |
| key_symbols | ✅ | 关键类名、函数名 |
| leader_description | ✅ | Leader Agent 功能描述，负责任务分解和协调 |
| worker_descriptions | ✅ | Worker Agent 列表，每个 Worker 的功能描述 |
| coordination_strategy | ✅ | 协调策略：hierarchical/parallel/sequential |
| skills | ✅ | 固定为 ["multi-agent-skill"] |
| smoke_tests | ✅ | 测试用例列表，multi_agent 模式下应包含测试命令，格式：["python main.py --test \"测试查询\""]，其中测试查询应基于用户需求生成 |

## 协调策略说明

| 策略 | 说明 |
|------|------|
| hierarchical | 层级式：Leader 分配任务，Workers 执行后汇报 |
| parallel | 并行式：多个 Workers 同时执行不同任务 |
| sequential | 顺序式：Workers 按顺序依次执行 |

## 示例

用户需求：「创建一个研究助手，能够搜索资料、分析内容、生成报告」

```json
{
    "files": ["config.py", "leader_agent.py", "worker_agents.py", "main.py"],
    "key_symbols": ["LeaderAgent", "SearchWorker", "AnalysisWorker", "ReportWorker", "main"],
    "skills": ["multi-agent-skill"],
    "include_references": {},
    "token_budget": 8000,
    "smoke_tests": ["python main.py --test \"搜索关于人工智能的最新研究\""],
    "leader_description": "研究协调者：分析用户研究需求，分配任务给 Workers，整合最终结果",
    "worker_descriptions": [
        "SearchWorker: 搜索相关资料和文献",
        "AnalysisWorker: 分析和总结搜索到的内容",
        "ReportWorker: 生成结构化的研究报告"
    ],
    "coordination_strategy": "sequential"
}
```
