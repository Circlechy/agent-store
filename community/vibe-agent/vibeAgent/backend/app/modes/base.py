"""
模式生成器基类

定义模式生成器的统一接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Callable
from pathlib import Path
from loguru import logger

from app.models.task import ModePlan
from app.skills.skill_manager import SkillManager


class ModeGenerator(ABC):
    """模式生成器基类"""
    
    # 类常量
    SKILL_NAME_MAP = {
        "workflow": "workflow-generation-skill",
        "react": "react-agent-skill",
        "multi_agent": "multi-agent-skill"
    }
    
    FILE_HINTS = {
        "config.py": "定义常量（WORKFLOW_ID、VERSION等）和配置函数（create_model_config、create_workflow_config）",
        "components.py": "实现所有组件的创建函数，每个组件都需要create_xxx_component函数",
        "workflow_builder.py": "构建工作流图，导入组件、添加节点、建立连接关系",
        "main.py": "入口文件，初始化运行时、创建工作流、处理用户输入",
        "local_agent.py": "定义Agent类，包含工具绑定、思考循环、行动执行逻辑",
        "leader_agent.py": "定义Leader Agent，负责任务分解和协调Worker",
        "worker_agents.py": "定义Worker Agents，每个Worker专注于特定任务类型"
    }
    
    FILE_GENERATION_REFS = {
        "config.py": "config-generation.md",
        "components.py": "component-generation.md",
        "workflow_builder.py": "workflow-builder-generation.md",
        "main.py": "main-generation.md",
        "tools_analysis.py": "tools-generation.md",
        "local_agent.py": "local-agent-generation.md",
        "leader_agent.py": "leader-agent-generation.md",
        "worker_agents.py": "worker-agents-generation.md"
    }
    
    @abstractmethod
    async def generate(self, plan: ModePlan, context: Dict[str, Any] = None) -> Dict[str, str]:
        """生成代码文件"""
        pass
    
    @abstractmethod
    def get_required_files(self) -> List[str]:
        """获取必需的文件列表"""
        pass
    
    def _load_generation_reference(self, file_name: str, context: Dict[str, Any]) -> str:
        """加载文件生成规则参考文档"""
        agent_mode = context.get("agent_mode")
        ref_name = self.FILE_GENERATION_REFS.get(file_name)
        
        if not agent_mode or not ref_name:
            return ""
        
        skill_name = self.SKILL_NAME_MAP.get(agent_mode)
        if not skill_name:
            return ""
        
        try:
            skill_manager = SkillManager()
            skill_data = skill_manager.load_skill(skill_name)
            if skill_data and ref_name in skill_data.get("references", {}):
                content = skill_data["references"][ref_name]
                return content[:1500] + "\n...（已截断）" if len(content) > 1500 else content
        except Exception as e:
            logger.debug(f"加载生成规则失败: {e}")
        
        return ""
    
    async def _generate_thinking(
        self,
        file_name: str,
        files: Dict[str, str],
        context: Dict[str, Any]
    ) -> str:
        """生成文件的思考过程（口语化、贴合实际，包含 skill 生成规则）"""
        llm_stream_fn = context.get("llm_stream_fn")
        on_thinking = context.get("on_thinking")
        user_input = context.get("user_input", "")
        
        if not llm_stream_fn or not on_thinking:
            return None
        
        file_hint = self.FILE_HINTS.get(file_name, "实现该文件的核心逻辑")
        existing = list(files.keys())
        existing_hint = f"\n已生成: {', '.join(existing)}" if existing else ""
        generation_ref_content = self._load_generation_reference(file_name, context)
        generation_ref_section = f"\n## 生成规范（参考此规范进行思考）\n{generation_ref_content}\n\n" if generation_ref_content else ""
        
        thinking_prompt = f"""## 当前任务
正在生成: {file_name}
职责: {file_hint}{generation_ref_section}## 上下文
需求: {user_input[:120]}{'...' if len(user_input) > 120 else ''}{existing_hint}

## 思考任务
作为程序员，用口语化方式思考这个文件的实现。**必须参考上面的生成规范**。

要求：
- 200-250字
- 口语化："好，这个文件..."、"根据规范..."、"首先..."、"然后..."、"注意..."
- **要结合生成规范思考**：需要定义什么函数、导入什么模块、关键逻辑、注意事项
- 想清楚：需要导入什么、定义什么函数/类、核心逻辑、和其他文件怎么配合
- 提一下可能的坑点

开始思考："""
        
        system_prompt = "你是资深程序员，用口语化的方式思考代码实现，像在脑子里过一遍方案。"
        
        accumulated = ""
        try:
            async for chunk in llm_stream_fn(thinking_prompt, system_prompt):
                accumulated += chunk
                on_thinking(file_name, chunk, accumulated)
            return accumulated
        except Exception as e:
            logger.warning(f"思考过程生成失败: {e}")
            return None
    
    async def _generate_file_with_thinking(
        self,
        file_name: str,
        generator_func: Callable,
        plan: ModePlan,
        files: Dict[str, str],
        context: Dict[str, Any]
    ) -> str:
        """生成单个文件（含思考过程）"""
        on_file_start = context.get("on_file_start")
        on_file_generated = context.get("on_file_generated")
        
        # 1. 发送开始事件
        if on_file_start:
            on_file_start(file_name)
        
        # 2. 生成思考过程
        thinking = await self._generate_thinking(file_name, files, context)
        if thinking:
            context["_current_thinking"] = thinking
        
        # 3. 生成文件内容
        content = await generator_func(plan, context)
        files[file_name] = content
        
        # 4. 发送完成事件
        if on_file_generated:
            on_file_generated(file_name, content)
        
        return content


def get_mode_generator(mode: str) -> ModeGenerator:
    """
    获取模式生成器
    
    Args:
        mode: 模式名称（react/workflow/multi_agent）
    
    Returns:
        ModeGenerator 实例
    """
    from app.models.task import AgentMode
    
    mode_enum = AgentMode(mode) if isinstance(mode, str) else mode
    
    if mode_enum == AgentMode.REACT:
        from app.modes.react_mode import ReActModeGenerator
        return ReActModeGenerator()
    elif mode_enum == AgentMode.WORKFLOW:
        from app.modes.workflow_mode import WorkflowModeGenerator
        return WorkflowModeGenerator()
    elif mode_enum == AgentMode.MULTI_AGENT:
        from app.modes.multi_agent_mode import MultiAgentModeGenerator
        return MultiAgentModeGenerator()
    else:
        raise ValueError(f"未知的模式: {mode}")
