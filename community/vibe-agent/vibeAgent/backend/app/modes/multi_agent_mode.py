"""
Multi-Agent 模式生成器

生成 HierarchicalGroup 代码
"""
from typing import Dict, Any, List, Optional, Callable
import re
from loguru import logger

from app.modes.base import ModeGenerator
from app.models.task import MultiAgentPlan
from app.skills.skill_manager import SkillManager


class MultiAgentModeGenerator(ModeGenerator):
    """Multi-Agent 模式生成器"""
    
    def __init__(self):
        """初始化 Multi-Agent 模式生成器"""
        self.skill_manager = SkillManager()
        self.skill_name = "multi-agent-skill"
    
    def get_required_files(self) -> List[str]:
        """获取必需的文件列表"""
        return ["config.py", "leader_agent.py", "worker_agents.py", "main.py"]
    
    async def generate(self, plan: MultiAgentPlan, context: Dict[str, Any] = None) -> Dict[str, str]:
        """生成 Multi-Agent 代码"""
        if plan is None:
            raise ValueError("MultiAgentPlan 不能为 None，请确保规划器成功生成计划")
        
        context = context or {}
        files = {}
        
        # 按顺序生成文件（使用基类的辅助方法）
        file_generators = [
            ("config.py", self._generate_config),
            ("leader_agent.py", self._generate_leader_agent),
            ("worker_agents.py", self._generate_worker_agents),
            ("main.py", self._generate_main),
        ]
        
        for file_name, generator_func in file_generators:
            context["generated_files"] = files
            await self._generate_file_with_thinking(file_name, generator_func, plan, files, context)
        
        logger.info(f"生成 Multi-Agent 代码: {len(files)} 个文件")
        return files
    
    async def _generate_config(self, plan: MultiAgentPlan, context: Dict[str, Any]) -> str:
        """
        生成 config.py
        
        使用 LLM 生成实际代码
        """
        # 获取 LLM 调用能力
        llm_call_fn = context.get("llm_call_fn")
        system_content = context.get("system_content", "")
        
        if not llm_call_fn or not system_content:
            raise ValueError("缺少 LLM 调用能力：context 中必须包含 'llm_call_fn' 和 'system_content'")
        
        logger.info("使用 LLM 生成 config.py")
        return await self._generate_config_with_llm(plan, context, llm_call_fn, system_content)
    
    async def _generate_config_with_llm(
        self,
        plan: MultiAgentPlan,
        context: Dict[str, Any],
        llm_call_fn: Callable,
        system_content: str
    ) -> str:
        """使用 LLM 生成 config.py 的实际代码"""
        # 从 skill 读取 config-generation.md（生成规则）
        skill_data = self.skill_manager.load_skill(self.skill_name)
        config_generation_ref = ""
        if skill_data and "config-generation.md" in skill_data.get("references", {}):
            config_generation_ref = skill_data["references"]["config-generation.md"]
            logger.info("✅ 已从 skill 读取 config-generation.md 生成规则")
        else:
            logger.warning("⚠️ 无法从 skill 读取 config-generation.md，将使用默认规则")
        
        # 构建 prompt（使用 skill 中的生成规则）
        prompt = f"""{system_content}

## 任务：生成 config.py

根据以下信息生成完整的 config.py 文件：

### Group 信息
- Group 名称：{context.get('workflow_name', 'default')}
- Leader 描述：{plan.leader_description or '主控制器，识别用户意图并分发任务'}
- Worker 描述：{', '.join(plan.worker_descriptions) if plan.worker_descriptions else 'Worker Agent（负责执行具体任务）'}
- 协调策略：{plan.coordination_strategy or 'hierarchical'}
- 用户输入：{context.get('query', context.get('user_input', ''))}

{config_generation_ref}

**重要约束（必须严格遵守）**：
1. **只输出 Python 代码**：不要输出 JSON、markdown 注释或解释文字
2. **代码块标记**：不要使用 ```python 或 ``` 标记
3. **注释规范**：所有解释信息必须以 # 或 \"\"\" 形式作为 Python 注释
4. **必需函数**：必须包含 create_model_config() 和 create_group_config() 函数

**输出格式要求（极其重要）**：
- 直接输出完整的 Python 代码
- 不要包含任何 markdown 代码块标记（如 ```python 或 ```）
- 不要包含任何 JSON 格式的数据
- 不要包含任何非代码的解释文字（解释信息应该作为 Python 注释）

请直接输出完整的 config.py 的 Python 代码。"""
        
        # 调用 LLM 生成代码
        code = await llm_call_fn(prompt, system_prompt=system_content)
        
        # 清理代码（移除 markdown 代码块标记）
        code = self._clean_code(code)
        
        logger.info(f"✅ 使用 LLM 生成 config.py 成功，代码长度: {len(code)} 字符")
        return code
    
    async def _generate_leader_agent(self, plan: MultiAgentPlan, context: Dict[str, Any]) -> str:
        """
        生成 leader_agent.py
        
        使用 LLM 生成实际代码
        """
        # 获取 LLM 调用能力
        llm_call_fn = context.get("llm_call_fn")
        system_content = context.get("system_content", "")
        
        if not llm_call_fn or not system_content:
            raise ValueError("缺少 LLM 调用能力：context 中必须包含 'llm_call_fn' 和 'system_content'")
        
        logger.info("使用 LLM 生成 leader_agent.py")
        return await self._generate_leader_agent_with_llm(plan, context, llm_call_fn, system_content)
    
    async def _generate_leader_agent_with_llm(
        self,
        plan: MultiAgentPlan,
        context: Dict[str, Any],
        llm_call_fn: Callable,
        system_content: str
    ) -> str:
        """使用 LLM 生成 leader_agent.py 的实际代码"""
        generated_files = context.get("generated_files", {})
        
        # 从 skill 读取 leader-agent-generation.md（生成规则）
        skill_data = self.skill_manager.load_skill(self.skill_name)
        leader_agent_generation_ref = ""
        if skill_data and "leader-agent-generation.md" in skill_data.get("references", {}):
            leader_agent_generation_ref = skill_data["references"]["leader-agent-generation.md"]
            logger.info("✅ 已从 skill 读取 leader-agent-generation.md 生成规则")
        else:
            logger.warning("⚠️ 无法从 skill 读取 leader-agent-generation.md，将使用默认规则")
        
        # 获取已生成的 config.py 完整内容（如果存在）
        config_code_section = ""
        if "config.py" in generated_files:
            config_code = generated_files["config.py"]
            config_code_section = f"""
**========== 已生成的 config.py 完整内容（必须严格参考）==========**
```python
{config_code}
```

**关键要求**：
1. 必须从 config 导入模型配置函数
2. 必须使用 config 中的函数来创建模型配置，不要重新定义
3. 确保导入语句正确：`from config import create_model_config`
**========== config.py 内容结束 ==========**

"""
        
        # 构建 prompt（使用 skill 中的生成规则）
        prompt = f"""{system_content}

## 任务：生成 leader_agent.py

根据以下信息生成完整的 leader_agent.py 文件：

### Group 信息
- Group 名称：{context.get('workflow_name', 'default')}
- Leader 描述：{plan.leader_description or '主控制器，识别用户意图并分发任务'}
- Worker 描述：{', '.join(plan.worker_descriptions) if plan.worker_descriptions else 'Worker Agent（负责执行具体任务）'}
- 协调策略：{plan.coordination_strategy or 'hierarchical'}
- 用户输入：{context.get('query', context.get('user_input', ''))}

{config_code_section}

{leader_agent_generation_ref}

**重要约束（必须严格遵守）**：
1. **只输出 Python 代码**：不要输出 JSON、markdown 注释或解释文字
2. **代码块标记**：不要使用 ```python 或 ``` 标记
3. **注释规范**：所有解释信息必须以 # 或 \"\"\" 形式作为 Python 注释
4. **必需函数**：必须包含 create_leader_agent() 函数，返回 (agent_id, leader_agent) 元组

**输出格式要求（极其重要）**：
- 直接输出完整的 Python 代码
- 不要包含任何 markdown 代码块标记（如 ```python 或 ```）
- 不要包含任何 JSON 格式的数据
- 不要包含任何非代码的解释文字（解释信息应该作为 Python 注释）

请直接输出完整的 leader_agent.py 的 Python 代码。"""
        
        # 调用 LLM 生成代码
        code = await llm_call_fn(prompt, system_prompt=system_content)
        
        # 清理代码（移除 markdown 代码块标记）
        code = self._clean_code(code)
        
        logger.info(f"✅ 使用 LLM 生成 leader_agent.py 成功，代码长度: {len(code)} 字符")
        return code
    
    async def _generate_worker_agents(self, plan: MultiAgentPlan, context: Dict[str, Any]) -> str:
        """
        生成 worker_agents.py
        
        使用 LLM 生成实际代码
        """
        # 获取 LLM 调用能力
        llm_call_fn = context.get("llm_call_fn")
        system_content = context.get("system_content", "")
        
        if not llm_call_fn or not system_content:
            raise ValueError("缺少 LLM 调用能力：context 中必须包含 'llm_call_fn' 和 'system_content'")
        
        logger.info("使用 LLM 生成 worker_agents.py")
        return await self._generate_worker_agents_with_llm(plan, context, llm_call_fn, system_content)
    
    async def _generate_worker_agents_with_llm(
        self,
        plan: MultiAgentPlan,
        context: Dict[str, Any],
        llm_call_fn: Callable,
        system_content: str
    ) -> str:
        """使用 LLM 生成 worker_agents.py 的实际代码"""
        generated_files = context.get("generated_files", {})
        
        # 从 skill 读取 worker-agents-generation.md（生成规则）
        skill_data = self.skill_manager.load_skill(self.skill_name)
        worker_agents_generation_ref = ""
        if skill_data and "worker-agents-generation.md" in skill_data.get("references", {}):
            worker_agents_generation_ref = skill_data["references"]["worker-agents-generation.md"]
            logger.info("✅ 已从 skill 读取 worker-agents-generation.md 生成规则")
        else:
            logger.warning("⚠️ 无法从 skill 读取 worker-agents-generation.md，将使用默认规则")
        
        # 获取已生成的文件内容（如果存在）
        previous_files_section = ""
        
        if "config.py" in generated_files:
            config_code = generated_files["config.py"]
            previous_files_section += f"""
**========== 已生成的 config.py 完整内容（必须严格参考）==========**
```python
{config_code}
```
**========== config.py 内容结束 ==========**

"""
        
        if "leader_agent.py" in generated_files:
            leader_agent_code = generated_files["leader_agent.py"]
            previous_files_section += f"""
**========== 已生成的 leader_agent.py 完整内容（必须严格参考）==========**
```python
{leader_agent_code}
```
**========== leader_agent.py 内容结束 ==========**

"""
        
        # 构建 Worker 描述信息
        workers_description = ""
        if plan.worker_descriptions:
            for i, desc in enumerate(plan.worker_descriptions):
                workers_description += f"- worker_{i}: {desc}\n"
        else:
            workers_description = "- worker_0: Worker Agent（负责执行具体任务）\n"
        
        # 构建 prompt（使用 skill 中的生成规则）
        prompt = f"""{system_content}

## 任务：生成 worker_agents.py

根据以下信息生成完整的 worker_agents.py 文件：

### Group 信息
- Group 名称：{context.get('workflow_name', 'default')}
- Leader 描述：{plan.leader_description or '主控制器，识别用户意图并分发任务'}
- Worker 描述：{', '.join(plan.worker_descriptions) if plan.worker_descriptions else 'Worker Agent（负责执行具体任务）'}
- 协调策略：{plan.coordination_strategy or 'hierarchical'}
- 用户输入：{context.get('query', context.get('user_input', ''))}

### Worker Agents 信息
{workers_description}

### 已生成的文件（必须严格参考）
以下是之前已生成的所有文件内容。在生成 worker_agents.py 时，**必须**参考这些文件，确保：
- 导入的模块和函数名称与实际文件中的定义完全一致
- 使用的常量和配置与实际文件中的定义完全一致
- 函数调用方式和参数与实际文件的接口完全一致

{previous_files_section}

{worker_agents_generation_ref}

**重要约束（必须严格遵守）**：
1. **只输出 Python 代码**：不要输出 JSON、markdown 注释或解释文字
2. **代码块标记**：不要使用 ```python 或 ``` 标记
3. **注释规范**：所有解释信息必须以 # 或 \"\"\" 形式作为 Python 注释
4. **必需函数**：必须包含 create_worker_agents() 函数，返回 dict[str, ReActAgent]

**输出格式要求（极其重要）**：
- 直接输出完整的 Python 代码
- 不要包含任何 markdown 代码块标记（如 ```python 或 ```）
- 不要包含任何 JSON 格式的数据
- 不要包含任何非代码的解释文字（解释信息应该作为 Python 注释）

请直接输出完整的 worker_agents.py 的 Python 代码。"""
        
        # 调用 LLM 生成代码
        code = await llm_call_fn(prompt, system_prompt=system_content)
        
        # 清理代码（移除 markdown 代码块标记）
        code = self._clean_code(code)
        
        logger.info(f"✅ 使用 LLM 生成 worker_agents.py 成功，代码长度: {len(code)} 字符")
        return code
    
    async def _generate_main(self, plan: MultiAgentPlan, context: Dict[str, Any]) -> str:
        """
        生成 main.py
        
        使用 LLM 生成实际代码
        """
        # 获取 LLM 调用能力
        llm_call_fn = context.get("llm_call_fn")
        system_content = context.get("system_content", "")
        
        if not llm_call_fn or not system_content:
            raise ValueError("缺少 LLM 调用能力：context 中必须包含 'llm_call_fn' 和 'system_content'")
        
        logger.info("使用 LLM 生成 main.py")
        return await self._generate_main_with_llm(plan, context, llm_call_fn, system_content)
    
    async def _generate_main_with_llm(
        self,
        plan: MultiAgentPlan,
        context: Dict[str, Any],
        llm_call_fn: Callable,
        system_content: str
    ) -> str:
        """使用 LLM 生成 main.py 的实际代码"""
        generated_files = context.get("generated_files", {})
        
        # 从 skill 读取 main-generation.md（生成规则）
        skill_data = self.skill_manager.load_skill(self.skill_name)
        main_generation_ref = ""
        if skill_data and "main-generation.md" in skill_data.get("references", {}):
            main_generation_ref = skill_data["references"]["main-generation.md"]
            logger.info("✅ 已从 skill 读取 main-generation.md 生成规则")
        else:
            logger.warning("⚠️ 无法从 skill 读取 main-generation.md，将使用默认规则")
        
        # 获取所有已生成文件的完整内容（按生成顺序）
        previous_files_section = ""
        
        if "config.py" in generated_files:
            config_code = generated_files["config.py"]
            previous_files_section += f"""
**========== 已生成的 config.py 完整内容（必须严格参考）==========**
```python
{config_code}
```
**========== config.py 内容结束 ==========**

"""
        
        if "leader_agent.py" in generated_files:
            leader_agent_code = generated_files["leader_agent.py"]
            previous_files_section += f"""
**========== 已生成的 leader_agent.py 完整内容（必须严格参考）==========**
```python
{leader_agent_code}
```
**========== leader_agent.py 内容结束 ==========**

"""
        
        if "worker_agents.py" in generated_files:
            worker_agents_code = generated_files["worker_agents.py"]
            previous_files_section += f"""
**========== 已生成的 worker_agents.py 完整内容（必须严格参考）==========**
```python
{worker_agents_code}
```

**关键要求**：
1. 必须从 worker_agents 导入 create_worker_agents 函数
2. 必须使用 create_worker_agents() 来创建 Worker Agents
3. 确保导入语句正确：`from worker_agents import create_worker_agents`
**========== worker_agents.py 内容结束 ==========**

"""
        
        # 构建 prompt（使用 skill 中的生成规则）
        prompt = f"""{system_content}

## 任务：生成 main.py

根据以下信息生成完整的 main.py 文件：

### Group 信息
- Group 名称：{context.get('workflow_name', 'default')}
- Leader 描述：{plan.leader_description or '主控制器，识别用户意图并分发任务'}
- Worker 描述：{', '.join(plan.worker_descriptions) if plan.worker_descriptions else 'Worker Agent（负责执行具体任务）'}
- 协调策略：{plan.coordination_strategy or 'hierarchical'}
- 用户输入：{context.get('query', context.get('user_input', ''))}

### 已生成的文件（必须严格参考）
以下是之前已生成的所有文件内容。在生成 main.py 时，**必须**参考这些文件，确保：
- 导入的模块和函数名称与实际文件中的定义完全一致
- 使用的常量和配置与实际文件中的定义完全一致
- 函数调用方式和参数与实际文件的接口完全一致

{previous_files_section}

{main_generation_ref}

**重要约束（必须严格遵守）**：
1. **只输出 Python 代码**：不要输出 JSON、markdown 注释或解释文字
2. **代码块标记**：不要使用 ```python 或 ``` 标记
3. **注释规范**：所有解释信息必须以 # 或 \"\"\" 形式作为 Python 注释
4. **必需函数**：必须包含 init_group(), run_test(), interactive_main() 和 extract_response() 函数

**输出格式要求（极其重要）**：
- 直接输出完整的 Python 代码
- 不要包含任何 markdown 代码块标记（如 ```python 或 ```）
- 不要包含任何 JSON 格式的数据
- 不要包含任何非代码的解释文字（解释信息应该作为 Python 注释）

请直接输出完整的 main.py 的 Python 代码。"""
        
        # 调用 LLM 生成代码
        code = await llm_call_fn(prompt, system_prompt=system_content)
        
        # 清理代码（移除 markdown 代码块标记）
        code = self._clean_code(code)
        
        logger.info(f"✅ 使用 LLM 生成 main.py 成功，代码长度: {len(code)} 字符")
        return code
    
    def _clean_code(self, code: str) -> str:
        """
        清理生成的代码，移除 markdown 代码块标记
        
        Args:
            code: 原始代码字符串
        
        Returns:
            清理后的代码字符串
        """
        # 移除 markdown 代码块标记
        code = re.sub(r'^```(?:python|py)?\s*\n', '', code, flags=re.MULTILINE)
        code = re.sub(r'\n```\s*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'^```\s*$', '', code, flags=re.MULTILINE)
        
        return code.strip()