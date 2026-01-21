"""
任务规划相关数据模型

定义 TaskPlan (L0) 和 ModePlan (L1) 两层计划模型
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class AgentMode(str, Enum):
    """Agent 生成模式"""
    REACT = "react"
    WORKFLOW = "workflow"
    MULTI_AGENT = "multi_agent"


class IntentType(str, Enum):
    """意图类型"""
    SIMPLE = "simple"  # 简单任务
    COMPLEX = "complex"  # 复杂任务


class CodebaseState(str, Enum):
    """代码库状态"""
    GREENFIELD = "greenfield"  # 新项目
    LEGACY = "legacy"  # 遗留项目


class TodoItem(BaseModel):
    """TODO 项（TaskPlan 中的单个任务）"""
    task_type: str = Field(description="任务类型：plan_mode/generate/test/fix")
    description: str = Field(description="任务描述")
    mode: Optional[AgentMode] = Field(default=None, description="Agent 模式")
    category: Optional[str] = Field(default=None, description="执行器类别")
    skills: List[str] = Field(default_factory=list, description="技能列表")
    expected_files: List[str] = Field(default_factory=list, description="预期文件列表")
    expected_outcome: str = Field(default="", description="预期结果")
    acceptance_checks: List[str] = Field(default_factory=list, description="验收检查项")
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=2, description="最大重试次数")
    status: str = Field(default="pending", description="状态：pending/running/completed/failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据（用于存储额外的任务信息，如错误信息、循环次数等）")


class TaskPlan(BaseModel):
    """任务计划（L0）- 主协调器生成的高层次 TODO 列表"""
    todos: List[TodoItem] = Field(description="TODO 列表")
    current_index: int = Field(default=0, description="当前执行索引")
    user_input: str = Field(default="", description="用户输入")
    agent_mode: Optional[AgentMode] = Field(default=None, description="Agent 模式（修改模式下可为 None）")
    intent_type: Optional[IntentType] = Field(default=None, description="意图类型")
    codebase_state: Optional[CodebaseState] = Field(default=None, description="代码库状态")
    
    def get_current_todo(self) -> Optional[TodoItem]:
        """获取当前 TODO"""
        if 0 <= self.current_index < len(self.todos):
            return self.todos[self.current_index]
        return None
    
    def mark_current_completed(self):
        """标记当前 TODO 为已完成"""
        todo = self.get_current_todo()
        if todo:
            todo.status = "completed"
    
    def mark_current_failed(self):
        """标记当前 TODO 为失败"""
        todo = self.get_current_todo()
        if todo:
            todo.status = "failed"
    
    def increment_retry(self) -> bool:
        """增加重试计数，返回是否可以继续重试"""
        todo = self.get_current_todo()
        if todo:
            todo.retry_count += 1
            return todo.retry_count <= todo.max_retries
        return False
    
    def advance(self) -> bool:
        """前进到下一个 TODO，返回是否成功前进"""
        self.current_index += 1
        return self.current_index < len(self.todos)
    
    def is_complete(self) -> bool:
        """检查是否完成所有 TODO"""
        return self.current_index >= len(self.todos)


class ModePlan(BaseModel):
    """模式计划（L1）- 面向具体模式的代码生成计划（基类）"""
    mode: AgentMode = Field(description="Agent 模式")
    files: List[str] = Field(description="预期文件清单")
    key_symbols: List[str] = Field(default_factory=list, description="关键类/函数/入口")
    skills: List[str] = Field(default_factory=list, description="技能列表")
    include_references: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="每个技能需要注入的 references 白名单"
    )
    token_budget: Optional[int] = Field(default=None, description="注入预算（token 上限）")
    smoke_tests: List[str] = Field(default_factory=list, description="最小可运行用例")


class WorkflowPlan(ModePlan):
    """Workflow 模式计划"""
    mode: AgentMode = Field(default=AgentMode.WORKFLOW, description="Agent 模式")
    workflow_description: str = Field(default="", description="工作流描述")
    components: List[Dict[str, Any]] = Field(default_factory=list, description="组件列表")
    workflow_structure: Dict[str, Any] = Field(default_factory=dict, description="工作流结构")


class ReActPlan(ModePlan):
    """ReAct Agent 模式计划"""
    mode: AgentMode = Field(default=AgentMode.REACT, description="Agent 模式")
    agent_description: str = Field(default="", description="Agent 描述")
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="工具列表")
    system_prompt: str = Field(default="", description="系统提示词")


class MultiAgentPlan(ModePlan):
    """Multi-Agent 模式计划"""
    mode: AgentMode = Field(default=AgentMode.MULTI_AGENT, description="Agent 模式")
    leader_description: str = Field(default="", description="Leader Agent 描述")
    worker_descriptions: List[str] = Field(default_factory=list, description="Worker Agent 描述列表")
    coordination_strategy: str = Field(default="", description="协调策略")
