"""
委托工具（DelegationTool）

作为 openJiuwen Tool 实现，统一的任务委托接口
"""
from typing import Dict, Any, Optional, List
from loguru import logger

from openjiuwen.core.utils.tool.base import Tool
from openjiuwen.core.utils.tool.schema import ToolInfo
from openjiuwen.core.utils.tool.param import Param
from openjiuwen.core.runtime.runtime import Runtime

from app.context.context_manager import ContextManager
from app.session.session_manager import SessionManager
from app.skills.skill_manager import SkillManager
from app.config.categories import get_category_config
from app.agents.executor_junior import create_executor_junior
from app.agents.planner_agent import PlannerAgent
from app.agents.librarian_agent import LibrarianAgent
from app.agents.tester_agent import TesterAgent
from app.agents.fixer_agent import FixerAgent
from app.models.agent_result import AgentResult


class DelegationTool(Tool):
    """
    委托工具 - 继承 openJiuwen.Tool
    
    作为 Facade 统一委托接口，支持两种委托模式：
    1. 类别模式（category-based）：动态创建执行器
    2. Agent 模式（agent-based）：调用预定义的专业化 Agent
    """
    
    def __init__(
        self,
        context_manager: ContextManager,
        session_manager: SessionManager,
        skill_manager: Optional[SkillManager] = None
    ):
        """
        初始化委托工具
        
        Args:
            context_manager: 上下文管理器
            session_manager: 会话管理器
            skill_manager: 技能管理器（可选）
        """
        super().__init__()
        self.name = 'delegate_task'  # Tool 实例必须有的 name 属性
        self.context_manager = context_manager
        self.session_manager = session_manager
        self.skill_manager = skill_manager or SkillManager()
        
        # 预定义的专业化 Agent（延迟初始化）
        self._specialized_agents: Dict[str, Any] = {}
        
        logger.info("初始化 DelegationTool")
    
    def get_tool_info(self) -> ToolInfo:
        """
        获取工具信息 - 实现 openJiuwen.Tool 抽象方法
        
        Returns:
            ToolInfo 实例
        """
        from openjiuwen.core.utils.tool.schema import Parameters
        
        return ToolInfo(
            type='function',
            name='delegate_task',
            description='委托任务给执行器或专业化Agent。支持两种模式：1) category模式：根据类别动态创建执行器；2) agent_type模式：调用预定义的专业化Agent（planner/librarian/tester/fixer）',
            parameters=Parameters(
                type='object',
                properties={
                    'category': Param(
                        name='category',
                        description='执行器类别（category模式）：general/coder/docgen',
                        param_type='string',
                        required=False
                    ),
                    'agent_type': Param(
                        name='agent_type',
                        description='Agent类型（agent模式）：planner/librarian/tester/fixer',
                        param_type='string',
                        required=False
                    ),
                    'prompt': Param(
                        name='prompt',
                        description='详细的任务描述',
                        param_type='string',
                        required=True
                    ),
                    'background': Param(
                        name='background',
                        description='是否后台执行（默认false）',
                        param_type='boolean',
                        required=False
                    ),
                    'skills': Param(
                        name='skills',
                        description='技能列表（可选）',
                        param_type='array',
                        required=False
                    ),
                    'include_references': Param(
                        name='include_references',
                        description='每个技能需要注入的references白名单（可选），格式：{"技能名": ["引用列表"]}',
                        param_type='object',
                        required=False,
                        schema=[Param(name='_', description='动态键值对，键为技能名，值为引用列表', param_type='array<string>', required=False)]
                    ),
                    'token_budget': Param(
                        name='token_budget',
                        description='注入预算（token上限，可选）',
                        param_type='number',
                        required=False
                    )
                },
                required=['prompt']
            )
        )
    
    def invoke(self, inputs: Dict, **kwargs) -> Dict:
        """
        同步调用 - 实现 openJiuwen.Tool 抽象方法
        
        Args:
            inputs: 工具输入
            **kwargs: 额外参数
        
        Returns:
            执行结果
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.ainvoke(inputs, **kwargs))
    
    async def ainvoke(self, inputs: Dict, **kwargs) -> Dict:
        """
        异步调用 - 实现 openJiuwen.Tool 抽象方法
        
        Args:
            inputs: 工具输入
            **kwargs: 额外参数
        
        Returns:
            执行结果
        """
        prompt = inputs.get("prompt", "")
        category = inputs.get("category")
        agent_type = inputs.get("agent_type")
        background = inputs.get("background", False)
        skills = inputs.get("skills", [])
        include_references = inputs.get("include_references")
        token_budget = inputs.get("token_budget")
        agent_mode = inputs.get("agent_mode")
        mode_plan = inputs.get("mode_plan")
        workflow_dir = inputs.get("workflow_dir", "")
        event_queue = inputs.get("_event_queue")  # 提取事件队列
        task_type = inputs.get("task_type")  # 任务类型（analyze_modification/modify_file）
        
        # 验证参数
        if not category and not agent_type:
            return AgentResult.failure_result(
                error="必须提供 category 或 agent_type 之一"
            ).to_dict()
        
        if category and agent_type:
            return AgentResult.failure_result(
                error="不能同时提供 category 和 agent_type"
            ).to_dict()
        
        # 路由到对应的处理方式
        if category:
            # 类别模式：动态创建执行器
            return await self._delegate_by_category(
                category=category,
                prompt=prompt,
                skills=skills,
                include_references=include_references,
                token_budget=token_budget,
                background=background,
                parent_runtime=kwargs.get("runtime"),
                agent_mode=agent_mode,
                mode_plan=mode_plan,
                workflow_dir=workflow_dir,
                event_queue=event_queue  # 传递事件队列
            )
        else:
            # Agent 模式：调用预定义的专业化 Agent
            return await self._delegate_by_agent_type(
                agent_type=agent_type,
                prompt=prompt,
                skills=skills,
                background=background,
                parent_runtime=kwargs.get("runtime"),
                workflow_dir=workflow_dir,
                task_type=task_type,  # 传递任务类型
                event_queue=event_queue,  # 传递事件队列
                agent_mode=agent_mode,  # 传递 agent_mode（特别是 PlannerAgent 需要）
                **{k: v for k, v in inputs.items() 
                   if k not in ["prompt", "category", "agent_type", "background", "skills", 
                               "include_references", "token_budget", "agent_mode", "mode_plan", 
                               "workflow_dir", "_event_queue", "task_type"]}  # 传递其他参数
            )
    
    async def _delegate_by_category(
        self,
        category: str,
        prompt: str,
        skills: List[str],
        include_references: Optional[Dict[str, List[str]]],
        token_budget: Optional[int],
        background: bool,
        parent_runtime: Optional[Runtime],
        agent_mode: Optional[str] = None,
        mode_plan: Optional[Dict] = None,
        workflow_dir: str = "",
        event_queue: Optional[Any] = None
    ) -> Dict:
        """
        类别模式委托：动态创建执行器
        
        Args:
            category: 类别名称
            prompt: 任务描述
            skills: 技能列表
            include_references: references 白名单
            token_budget: token 预算
            background: 是否后台执行
            parent_runtime: 父 Runtime
            agent_mode: Agent 模式
            mode_plan: 模式计划
            workflow_dir: 工作流目录
        
        Returns:
            执行结果
        """
        try:
            # 1. 解析类别配置
            category_config = get_category_config(category)
            
            # 2. 构建系统内容（技能 + 类别提示）
            system_content = self._build_system_content(
                skills=skills,
                include_references=include_references,
                token_budget=token_budget,
                category_prompt_append=category_config.prompt_append
            )
            
            # 3. 创建子会话
            session_id = self.session_manager.create_session(
                parent_runtime=parent_runtime,
                title=f"Task: {category}"
            )
            
            # 4. 创建执行器
            executor = create_executor_junior(
                category=category,
                system_content=system_content,
                context_manager=self.context_manager
            )
            
            # 5. 创建子 Runtime（如果需要）
            if parent_runtime:
                from openjiuwen.core.runtime.agent import AgentRuntime
                child_runtime = AgentRuntime(session_id=session_id)
            else:
                child_runtime = executor._runtime
            
            # 6. 执行任务（传递 agent_mode, mode_plan, workflow_dir）
            # 🔍 [DEBUG] 委托工具传递给执行器的输入
            logger.info(f"🔍 [DEBUG] DelegationTool -> ExecutorJunior:")
            logger.info(f"🔍 [DEBUG]   category: {category}")
            logger.info(f"🔍 [DEBUG]   agent_mode: {agent_mode}")
            logger.info(f"🔍 [DEBUG]   workflow_dir: {workflow_dir}")
            logger.info(f"🔍 [DEBUG]   mode_plan: {str(mode_plan)[:300] if mode_plan else 'None'}...")
            
            # 构建 executor.invoke 的 inputs
            executor_inputs = {
                "query": prompt,
                "agent_mode": agent_mode,
                "mode_plan": mode_plan,
                "workflow_dir": workflow_dir
            }
            # 如果有事件队列，传递给执行器
            if event_queue is not None:
                executor_inputs["_event_queue"] = event_queue
            
            result = await executor.invoke(
                inputs=executor_inputs,
                runtime=child_runtime
            )
            
            # 🔍 [DEBUG] 执行器返回结果
            logger.info(f"🔍 [DEBUG] ExecutorJunior 返回:")
            logger.info(f"🔍 [DEBUG]   result keys: {list(result.keys()) if result else 'None'}")
            logger.info(f"🔍 [DEBUG]   success: {result.get('success') if result else 'N/A'}")
            
            return result
        
        except Exception as e:
            logger.error(f"类别模式委托失败: {e}", exc_info=True)
            return AgentResult.failure_result(error=str(e)).to_dict()
    
    async def _delegate_by_agent_type(
        self,
        agent_type: str,
        prompt: str,
        skills: List[str],
        background: bool,
        parent_runtime: Optional[Runtime],
        workflow_dir: str = "",
        task_type: Optional[str] = None,
        event_queue: Optional[Any] = None,
        agent_mode: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        Agent 模式委托：调用预定义的专业化 Agent
        
        Args:
            agent_type: Agent 类型（planner/librarian/tester/fixer）
            prompt: 任务描述
            skills: 技能列表（可选，某些 Agent 可能不需要）
            background: 是否后台执行
            parent_runtime: 父 Runtime
            workflow_dir: 工作流目录
            task_type: 任务类型（用于特殊处理，如 analyze_modification/modify_file）
            event_queue: 事件队列（可选）
            **kwargs: 其他参数（传递给 Agent）
        
        Returns:
            执行结果
        """
        try:
            # 1. 获取或创建专业化 Agent
            agent = self._get_specialized_agent(agent_type)
            if not agent:
                return AgentResult.failure_result(
                    error=f"未知的 Agent 类型: {agent_type}"
                ).to_dict()
            
            # 2. 为 FixerAgent 传递 session_manager
            if agent_type == "fixer" and hasattr(agent, "session_manager") and not agent.session_manager:
                agent.session_manager = self.session_manager
            
            # 3. 创建子会话
            session_id = self.session_manager.create_session(
                parent_runtime=parent_runtime,
                title=f"Task: {agent_type}"
            )
            
            # 4. 创建子 Runtime
            if parent_runtime:
                from openjiuwen.core.runtime.agent import AgentRuntime
                child_runtime = AgentRuntime(session_id=session_id)
            else:
                child_runtime = agent._runtime
            
            # 5. 构建输入（根据任务类型）
            inputs = {"query": prompt, "workflow_dir": workflow_dir}
            
            # 如果指定了 task_type，添加任务类型标识
            if task_type:
                inputs["task_type"] = task_type
            
            # 如果指定了 agent_mode，传递给 Agent（特别是 PlannerAgent 需要）
            if agent_mode:
                inputs["agent_mode"] = agent_mode
            
            # 如果有事件队列，传递给 Agent
            if event_queue is not None:
                inputs["_event_queue"] = event_queue
            
            # 添加其他 kwargs
            inputs.update(kwargs)
            
            # 6. 执行任务
            result = await agent.invoke(
                inputs=inputs,
                runtime=child_runtime
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Agent 模式委托失败: {e}", exc_info=True)
            return AgentResult.failure_result(error=str(e)).to_dict()
    
    def _build_system_content(
        self,
        skills: List[str],
        include_references: Optional[Dict[str, List[str]]],
        token_budget: Optional[int],
        category_prompt_append: str
    ) -> str:
        """
        构建系统内容（技能 + 类别提示）
        
        Args:
            skills: 技能列表
            include_references: references 白名单
            token_budget: token 预算
            category_prompt_append: 类别提示追加
        
        Returns:
            系统内容字符串
        """
        parts = []
        
        # 1. 技能内容
        if skills:
            skill_content = self.skill_manager.get_multiple_skills_content(
                skill_names=skills,
                include_references=include_references,
                token_budget=token_budget
            )
            if skill_content:
                parts.append(skill_content)
        
        # 2. 类别提示追加
        if category_prompt_append:
            parts.append(f"## Category Guidance\n\n{category_prompt_append}")
        
        return "\n\n".join(parts)
    
    def _get_specialized_agent(self, agent_type: str):
        """
        获取或创建专业化 Agent
        
        Args:
            agent_type: Agent 类型
        
        Returns:
            Agent 实例
        """
        if agent_type in self._specialized_agents:
            return self._specialized_agents[agent_type]
        
        # 延迟创建 Agent
        from openjiuwen.agent.config.base import AgentConfig
        from openjiuwen.core.component.common.configs.model_config import ModelConfig
        from openjiuwen.core.utils.llm.base import BaseModelInfo
        from app.config.settings import get_settings
        
        settings = get_settings()
        
        model_config = ModelConfig(
            model_provider=settings.model.provider,
            model_info=BaseModelInfo(
                api_key=settings.model.api_key,
                api_base=settings.model.api_base,
                model=settings.model.model_name,  # 使用别名 'model' 而非 'model_name'
                temperature=0.3,
                top_p=0.9,
                timeout=settings.model.timeout
            )
        )
        
        agent_config = AgentConfig(
            id=f"{agent_type}_agent",
            version="1.0.0",
            description=f"{agent_type} Agent",
            model=model_config
        )
        
        if agent_type == "planner":
            agent = PlannerAgent(agent_config, self.context_manager)
        elif agent_type == "librarian":
            agent = LibrarianAgent(agent_config, self.context_manager)
        elif agent_type == "tester":
            from app.sandbox.sandbox import Sandbox
            agent = TesterAgent(agent_config, self.context_manager, Sandbox())
        elif agent_type == "fixer":
            agent = FixerAgent(agent_config, self.context_manager, self.session_manager, self.skill_manager)
        else:
            return None
        
        self._specialized_agents[agent_type] = agent
        return agent
