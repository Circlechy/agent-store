"""
规划 Agent（PlannerAgent）

负责生成详细的模式计划（ModePlan）
基于 Skill 的 plan-schema.md 生成规划，而非硬编码提示词
"""
from typing import Dict, Any, Optional, AsyncIterator
from pathlib import Path
from loguru import logger

from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.agent.config.base import AgentConfig

from app.agents.base import VibeBaseAgent
from app.context.context_manager import ContextManager
from app.models.agent_result import AgentResult
from app.models.task import ModePlan, WorkflowPlan, ReActPlan, MultiAgentPlan, AgentMode
from app.utils import normalize_agent_mode
from app.config.tools_config import get_available_tools, format_tools_for_planning, load_available_tools


# Skill 名称映射
SKILL_MAP = {
    AgentMode.WORKFLOW: "workflow-generation-skill",
    AgentMode.REACT: "react-agent-skill",
    AgentMode.MULTI_AGENT: "multi-agent-skill"
}


class PlannerAgent(VibeBaseAgent):
    """
    规划 Agent - 继承 openJiuwen.BaseAgent
    
    职责：生成详细的模式计划（ModePlan）
    关键约束：
    - ❌ 禁止使用 delegate_task 工具
    - ✅ 可以使用其他所有工具
    """
    
    def __init__(
        self,
        agent_config: AgentConfig,
        context_manager: Optional[ContextManager] = None
    ):
        """
        初始化规划 Agent
        
        Args:
            agent_config: Agent 配置（必须包含 model）
            context_manager: 上下文管理器
        """
        super().__init__(agent_config, context_manager)
        logger.info("初始化 PlannerAgent")
    
    async def invoke(self, inputs: Dict, runtime: Runtime = None) -> Dict:
        """
        实现 openJiuwen 的 invoke 接口
        
        Args:
            inputs: 输入数据 {query, agent_mode, user_input, ...}
            runtime: Runtime 实例
        
        Returns:
            执行结果 {mode_plan: ModePlan}
        """
        try:
            query = inputs.get("query", "")
            agent_mode_str = inputs.get("agent_mode", "workflow")
            user_input = inputs.get("user_input", query)
            
            # 规范化 agent_mode（向后兼容：将 "agent" 映射到 "react"）
            agent_mode_str = normalize_agent_mode(agent_mode_str)
            
            # 🔍 [DEBUG] 规划器输入
            logger.info(f"🔍 [DEBUG] PlannerAgent.invoke 输入:")
            logger.info(f"🔍 [DEBUG]   query: {query[:200]}..." if len(query) > 200 else f"🔍 [DEBUG]   query: {query}")
            logger.info(f"🔍 [DEBUG]   agent_mode: {agent_mode_str}")
            
            agent_mode = AgentMode(agent_mode_str)
            
            # 生成模式计划
            mode_plan = await self._plan_mode(user_input, agent_mode, inputs)
            
            # 🔍 [DEBUG] 规划器输出
            plan_dict = mode_plan.model_dump(exclude_none=False, exclude_unset=False)
            logger.info(f"🔍 [DEBUG] PlannerAgent.invoke 输出:")
            logger.info(f"🔍 [DEBUG]   mode_plan.files: {plan_dict.get('files', [])}")
            logger.info(f"🔍 [DEBUG]   mode_plan.key_symbols: {plan_dict.get('key_symbols', [])}")
            logger.info(f"🔍 [DEBUG]   mode_plan.skills: {plan_dict.get('skills', [])}")
            # 🔍 [DEBUG] 检查 components 字段
            if isinstance(mode_plan, WorkflowPlan):
                components = plan_dict.get('components', [])
                logger.info(f"🔍 [DEBUG]   mode_plan.components: type={type(components).__name__}, len={len(components) if isinstance(components, list) else 'N/A'}")
                if components:
                    logger.info(f"🔍 [DEBUG]   ✅ components 包含 {len(components)} 个组件")
                else:
                    logger.warning(f"🔍 [DEBUG]   ⚠️ components 为空或不存在")
            
            return AgentResult.success_result(
                data={"mode_plan": plan_dict},
                metadata={"agent_mode": agent_mode_str}
            ).to_dict()
        
        except Exception as e:
            logger.error(f"规划失败: {e}", exc_info=True)
            return AgentResult.failure_result(error=str(e)).to_dict()
    
    async def stream(self, inputs: Dict, runtime: Runtime = None) -> AsyncIterator[Any]:
        """实现 openJiuwen 的 stream 接口"""
        result = await self.invoke(inputs, runtime)
        yield result
    
    async def _plan_mode(
        self,
        user_input: str,
        agent_mode: AgentMode,
        context: Dict[str, Any]
    ) -> ModePlan:
        """
        规划模式生成步骤
        
        Args:
            user_input: 用户输入
            agent_mode: Agent 模式
            context: 上下文信息
        
        Returns:
            ModePlan 实例
        """
        # 构建规划提示词
        prompt = self._build_planning_prompt(user_input, agent_mode, context)
        system_prompt = self._get_system_prompt(agent_mode)
        
        # 调用 LLM 生成计划
        response = await self._call_llm(prompt, system_prompt=system_prompt, runtime=self._runtime)
        # print(f"********* response: {response}")
        
        # 解析响应为 ModePlan
        mode_plan = self._parse_plan_response(response, agent_mode, user_input)
        
        return mode_plan
    
    def _load_plan_schema(self, agent_mode: AgentMode) -> str:
        """
        从 Skill 加载 plan-schema.md
        
        Args:
            agent_mode: Agent 模式
        
        Returns:
            plan-schema.md 的内容
        """
        # 🔍 [DEBUG] 检查 agent_mode 和 SKILL_MAP
        logger.info(f"🔍 [DEBUG] _load_plan_schema: agent_mode={agent_mode}, type={type(agent_mode)}, value={agent_mode.value if hasattr(agent_mode, 'value') else agent_mode}")
        logger.info(f"🔍 [DEBUG] SKILL_MAP keys: {[str(k) + '=' + k.value for k in SKILL_MAP.keys()]}")
        logger.info(f"🔍 [DEBUG] agent_mode in SKILL_MAP: {agent_mode in SKILL_MAP}")
        
        # 确保正确匹配：直接使用 agent_mode 作为键
        if agent_mode in SKILL_MAP:
            skill_name = SKILL_MAP[agent_mode]
            logger.info(f"✅ [DEBUG] 从 SKILL_MAP 找到匹配: {agent_mode} -> {skill_name}")
        else:
            # 如果不在 SKILL_MAP 中，记录错误并返回空字符串
            logger.error(f"❌ [ERROR] agent_mode {agent_mode} (value={agent_mode.value if hasattr(agent_mode, 'value') else agent_mode}) 不在 SKILL_MAP 中！")
            logger.error(f"❌ [ERROR] 可用的 agent_mode: {[k.value for k in SKILL_MAP.keys()]}")
            return ""
        
        # 计算 skills 目录路径
        # backend_v3/app/agents/planner_agent.py -> backend_v3/skills/
        skills_dir = Path(__file__).parent.parent.parent / "skills"
        schema_path = skills_dir / skill_name / "references" / "plan-schema.md"
        
        logger.info(f"🔍 [DEBUG] 尝试加载 schema: {schema_path}")
        logger.info(f"🔍 [DEBUG] schema_path.exists(): {schema_path.exists()}")
        
        if schema_path.exists():
            content = schema_path.read_text(encoding="utf-8")
            logger.info(f"✅ 成功加载 Skill schema: {schema_path} (长度: {len(content)} 字符)")
            return content
        else:
            logger.warning(f"⚠️ Skill schema 不存在: {schema_path}，使用默认提示词")
            # 列出实际存在的 skills 目录，帮助调试
            if skills_dir.exists():
                existing_skills = [d.name for d in skills_dir.iterdir() if d.is_dir()]
                logger.warning(f"⚠️ 实际存在的 skills: {existing_skills}")
            return ""
    
    def _build_available_tools_section(self, agent_mode: AgentMode) -> str:
        """
        构建可用工具列表部分（仅用于 REACT 模式）
        
        Args:
            agent_mode: Agent 模式
        
        Returns:
            可用工具列表的字符串，如果不是 REACT 模式则返回空字符串
        """
        if agent_mode == AgentMode.WORKFLOW:
            tools_info_section = load_available_tools()
            return f"""## 可用外部工具
{tools_info_section}
- 如果用户明确要求调用真实的外部API或者工作流某个功能确实需要使用外部API，且有合适的工具可用，则生成ToolComponent。
- 如果没有合适的工具可用，禁止生成ToolComponent，禁止自行编造工具。
- 如果确定使用ToolComponent，确保component_name字段为具体的工具名称(name字段)。"""
            

        if agent_mode != AgentMode.REACT:
            return ""
        
        available_tools = get_available_tools()
        if available_tools:
            tools_section = f"\n## 可用工具列表\n\n{format_tools_for_planning(available_tools)}\n"
            logger.info(f"✅ 已加载 {len(available_tools)} 个可用工具到规划提示词")
            return tools_section
        else:
            logger.warning("⚠️ 未找到可用工具，规划时将不使用工具")
            return "\n## 可用工具列表\n\n无可用工具（不使用工具）\n\n"
    
    def _build_planning_prompt(
        self,
        user_input: str,
        agent_mode: AgentMode,
        context: Dict[str, Any]
    ) -> str:
        """构建规划提示词 - 从 Skill 的 plan-schema.md 加载"""
        
        plan_schema = self._load_plan_schema(agent_mode)
        available_tools_section = self._build_available_tools_section(agent_mode)
        
        if plan_schema:
            additional_instructions = self._get_additional_instructions(agent_mode)
            prompt = f"""{user_input}
{available_tools_section}

## 规划要求
{plan_schema}

{additional_instructions}

请根据上述用户需求和规划要求，直接输出符合格式的 JSON。
"""
        else:
            skill_name = SKILL_MAP.get(agent_mode, "unknown-skill")
            if skill_name == "unknown-skill":
                logger.error(f"❌ agent_mode {agent_mode} 不在 SKILL_MAP 中，无法生成提示词")
            
            prompt = f"""根据用户需求生成 {agent_mode.value} 模式的代码规划 JSON。

## 用户需求
{user_input}
{available_tools_section}## 要求
使用 {skill_name} 技能，输出包含 files, key_symbols, skills 等字段的 JSON。
"""
        
        return prompt
    
    def _get_additional_instructions(self, agent_mode: AgentMode) -> str:
        """
        获取模式特定的额外说明
        
        Args:
            agent_mode: Agent 模式
        
        Returns:
            额外说明字符串（如果不需要则返回空字符串）
        """
        if agent_mode != AgentMode.REACT:
            return ""
        
        available_tools = get_available_tools()
        has_tools = bool(available_tools)
        
        base_instructions = """
**重要：关于 tools 字段的说明**
- tools 字段只应该包含工具的需求描述（name、description、parameters）
- **不要**包含具体的实现细节，如 path、method、headers 等
- 这些实现细节将在生成阶段根据可用工具列表自动生成
- 参数描述应该包含类型和是否必需，例如："city": "城市名称（string，必需）"
"""
        
        if has_tools:
            return base_instructions + """
- **必须从上述"可用工具列表"中选择工具**，不能自己创造工具
- 根据用户需求，从可用工具列表中选择合适的工具（可以是一个或多个，也可以为空数组 []）
- **工具名称（name）必须与可用工具列表中的 name 字段完全一致**
- 如果用户需求不需要工具，可以返回空数组 []
"""
        else:
            return base_instructions + """
- 当前没有可用工具，请返回空数组 []
"""
    
    def _get_system_prompt(self, agent_mode: AgentMode) -> str:
        """获取系统提示词"""
        if agent_mode == AgentMode.WORKFLOW:
            return """你是 openJiuwen 框架的代码规划专家。

核心规则：
1. 只输出 JSON，不要任何其他文字
2. 严格按照用户消息中的格式要求输出
3. **所有必填字段必须填写，特别是 components 字段**
4. **components 字段是必填的，绝对不能为空数组或缺失**
5. **components 必须包含至少 Start 和 End 组件，以及必要的中间组件**
6. 参考示例来理解正确的格式

你的输出将被直接解析为 JSON。如果缺少必填字段（特别是 components），将导致后续代码生成失败。"""
        else:
            return """你是 openJiuwen 框架的代码规划专家。

核心规则：
1. 只输出 JSON，不要任何其他文字
2. 严格按照用户消息中的格式要求输出
3. 所有字段必须填写
4. 参考示例来理解正确的格式

你的输出将被直接解析为 JSON。"""
    
    def _parse_plan_response(
        self,
        response: str,
        agent_mode: AgentMode,
        user_input: str
    ) -> ModePlan:
        """解析 LLM 响应为 ModePlan"""
        import json
        import re
        
        # 🔍 [DEBUG] 原始 LLM 响应
        logger.info(f"🔍 [DEBUG] LLM 原始响应长度: {len(response)}")
        logger.info(f"🔍 [DEBUG] LLM 响应前500字符: {response[:500]}...")
        
        # 尝试多种方式提取 JSON
        plan_data = {}
        
        # 方式1: 尝试直接解析（如果响应就是纯 JSON）
        try:
            plan_data = json.loads(response.strip())
            logger.info(f"🔍 [DEBUG] 直接解析 JSON 成功")
        except json.JSONDecodeError:
            # 方式2: 提取 ```json ... ``` 代码块
            code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
            match = re.search(code_block_pattern, response, re.DOTALL)
            if match:
                try:
                    plan_data = json.loads(match.group(1))
                    logger.info(f"🔍 [DEBUG] 从代码块提取 JSON 成功")
                except json.JSONDecodeError as e:
                    logger.warning(f"🔍 [DEBUG] 代码块 JSON 解析失败: {e}")
            
            # 方式3: 提取第一个 { 到最后一个 } 之间的内容
            if not plan_data:
                brace_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                matches = re.findall(brace_pattern, response, re.DOTALL)
                for m in matches:
                    try:
                        plan_data = json.loads(m)
                        logger.info(f"🔍 [DEBUG] 从大括号提取 JSON 成功")
                        break
                    except json.JSONDecodeError:
                        continue
        
        # 🔍 [DEBUG] 解析结果
        if plan_data:
            logger.info(f"🔍 [DEBUG] 解析到的字段: {list(plan_data.keys())}")
            # 验证关键字段
            if agent_mode == AgentMode.WORKFLOW:
                if "components" not in plan_data or not plan_data.get("components"):
                    logger.error(f"🔍 [DEBUG] ❌ 关键错误：plan_data 中缺少 components 字段或 components 为空")
                    logger.error(f"🔍 [DEBUG] plan_data 内容: {plan_data}")
                    raise ValueError(
                        f"PlannerAgent 生成的计划中缺少 components 字段或 components 为空。"
                        f"这是必填字段，请检查 PlannerAgent 的 prompt 和 LLM 响应。"
                        f"解析到的字段: {list(plan_data.keys())}"
                    )
                else:
                    logger.info(f"🔍 [DEBUG] ✅ components 字段存在，包含 {len(plan_data['components'])} 个组件")
        else:
            logger.error(f"🔍 [DEBUG] ❌ JSON 解析完全失败，无法生成计划")
            raise ValueError(
                f"PlannerAgent 无法解析 LLM 响应为有效的 JSON。"
                f"请检查 LLM 响应格式和解析逻辑。"
            )
        
        # 根据模式创建对应的 Plan
        if agent_mode == AgentMode.WORKFLOW:
            components = plan_data.get("components", [])
            if not components:
                raise ValueError(
                    f"WorkflowPlan.components 不能为空。"
                    f"PlannerAgent 应该生成组件列表，但当前 components 为空。"
                    f"请检查 PlannerAgent 的 prompt 和 LLM 响应。"
                )
            
            return WorkflowPlan(
                mode=agent_mode,
                files=plan_data.get("files", ["config.py", "components.py", "workflow_builder.py", "main.py"]),
                key_symbols=plan_data.get("key_symbols", []),
                skills=plan_data.get("skills", ["workflow-generation-skill"]),
                include_references=plan_data.get("include_references", {}),
                token_budget=plan_data.get("token_budget", 8000),
                smoke_tests=plan_data.get("smoke_tests", []),
                workflow_description=plan_data.get("workflow_description", user_input),
                components=components,  # 使用验证后的 components
                workflow_structure=plan_data.get("workflow_structure", {})
            )
        elif agent_mode == AgentMode.REACT:
            return ReActPlan(
                mode=agent_mode,
                files=plan_data.get("files", ["config.py", "local_agent.py", "main.py"]),
                key_symbols=plan_data.get("key_symbols", []),
                skills=plan_data.get("skills", ["react-agent-skill"]),
                include_references=plan_data.get("include_references", {}),
                token_budget=plan_data.get("token_budget", 8000),
                smoke_tests=plan_data.get("smoke_tests", []),
                agent_description=plan_data.get("agent_description", user_input),
                tools=plan_data.get("tools", []),
                system_prompt=plan_data.get("system_prompt", "")
            )
        else:  # MULTI_AGENT
            return MultiAgentPlan(
                mode=agent_mode,
                files=plan_data.get("files", ["config.py", "leader_agent.py", "worker_agent.py", "main.py"]),
                key_symbols=plan_data.get("key_symbols", []),
                skills=plan_data.get("skills", ["multi-agent-skill"]),
                include_references=plan_data.get("include_references", {}),
                token_budget=plan_data.get("token_budget", 8000),
                smoke_tests=plan_data.get("smoke_tests", []),
                leader_description=plan_data.get("leader_description", user_input),
                worker_descriptions=plan_data.get("worker_descriptions", []),
                coordination_strategy=plan_data.get("coordination_strategy", "")
            )
