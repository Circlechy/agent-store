"""
ReAct Agent 模式生成器

生成 ReActAgent 代码
"""
from typing import Dict, Any, List, Optional, Callable
import re
from loguru import logger

from app.modes.base import ModeGenerator
from app.models.task import ReActPlan
from app.skills.skill_manager import SkillManager
from app.config.tools_config import get_available_tools, get_tool_by_name


class ReActModeGenerator(ModeGenerator):
    """ReAct Agent 模式生成器"""
    
    def __init__(self):
        """初始化 ReAct 模式生成器"""
        self.skill_manager = SkillManager()
        self.skill_name = "react-agent-skill"
    
    def get_required_files(self) -> List[str]:
        """获取必需的文件列表"""
        # 总是包含 tools_analysis.py（即使工具列表为空，也会生成空函数）
        return ["config.py", "tools_analysis.py", "local_agent.py", "main.py"]
    
    async def generate(self, plan: ReActPlan, context: Dict[str, Any] = None) -> Dict[str, str]:
        """生成 ReActAgent 代码"""
        if plan is None:
            raise ValueError("ReActPlan 不能为 None，请确保规划器成功生成计划")
        
        context = context or {}
        files = {}
        
        # 按顺序生成文件（使用基类的辅助方法）
        file_generators = [
            ("config.py", self._generate_config),
            ("tools_analysis.py", self._generate_tools),
            ("local_agent.py", self._generate_local_agent),
            ("main.py", self._generate_main),
        ]
        
        for file_name, generator_func in file_generators:
            context["generated_files"] = files
            await self._generate_file_with_thinking(file_name, generator_func, plan, files, context)
        
        logger.info(f"生成 ReAct Agent 代码: {len(files)} 个文件")
        return files
    
    async def _generate_config(self, plan: ReActPlan, context: Dict[str, Any]) -> str:
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
        plan: ReActPlan,
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

### Agent 信息
- Agent 名称：{plan.agent_description or 'react_agent'}
- Agent 描述：{plan.agent_description}
- 用户输入：{context.get('query', context.get('user_input', ''))}

{config_generation_ref}

**重要约束（必须严格遵守）**：
1. **只输出 Python 代码**：不要输出 JSON、markdown 注释或解释文字
2. **代码块标记**：不要使用 ```python 或 ``` 标记
3. **注释规范**：所有解释信息必须以 # 或 \"\"\" 形式作为 Python 注释
4. **必需函数**：必须包含 create_model_config() 函数

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
    
    async def _generate_tools(self, plan: ReActPlan, context: Dict[str, Any]) -> str:
        """
        生成 tools_analysis.py
        
        使用 LLM 生成实际代码
        """
        # 获取 LLM 调用能力
        llm_call_fn = context.get("llm_call_fn")
        system_content = context.get("system_content", "")
        
        if not llm_call_fn or not system_content:
            raise ValueError("缺少 LLM 调用能力：context 中必须包含 'llm_call_fn' 和 'system_content'")
        
        logger.info("使用 LLM 生成 tools_analysis.py")
        return await self._generate_tools_with_llm(plan, context, llm_call_fn, system_content)
    
    async def _generate_tools_with_llm(
        self,
        plan: ReActPlan,
        context: Dict[str, Any],
        llm_call_fn: Callable,
        system_content: str
    ) -> str:
        """使用 LLM 生成 tools_analysis.py 的实际代码"""
        # 从 skill 读取 tools-generation.md（生成规则）
        skill_data = self.skill_manager.load_skill(self.skill_name)
        tools_generation_ref = ""
        if skill_data and "tools-generation.md" in skill_data.get("references", {}):
            tools_generation_ref = skill_data["references"]["tools-generation.md"]
            logger.info("✅ 已从 skill 读取 tools-generation.md 生成规则")
        else:
            logger.warning("⚠️ 无法从 skill 读取 tools-generation.md，将使用默认规则")
        
        # 加载可用工具列表
        available_tools = get_available_tools()
        
        # 构建工具信息（包含完整实现细节）
        tools_info = self._build_tools_info_with_details(plan.tools, available_tools)
        
        # 构建 prompt（使用 skill 中的生成规则）
        prompt = f"""{system_content}

## 任务：生成 tools_analysis.py

根据以下信息生成完整的 tools_analysis.py 文件：

### Agent 信息
- Agent 名称：{plan.agent_description or 'react_agent'}
- Agent 描述：{plan.agent_description}
- 用户输入：{context.get('query', context.get('user_input', ''))}

### 工具信息（包含完整实现细节）
{tools_info}

**重要说明**：
- 上述工具信息包含完整的实现细节（name、description、parameters、path、method、headers 等）
- **必须严格按照上述工具信息中的实现细节生成代码**，不要修改 path、method、headers 等字段
- 所有工具都应该是 RestfulApi 类型
- 使用工具信息中提供的 path、method、headers 来创建 RestfulApi 工具实例

{tools_generation_ref}

**重要约束（必须严格遵守）**：
1. **只输出 Python 代码**：不要输出 JSON、markdown 注释或解释文字
2. **代码块标记**：不要使用 ```python 或 ``` 标记
3. **注释规范**：所有解释信息必须以 # 或 \"\"\" 形式作为 Python 注释
4. **必需函数**：必须包含 get_all_tools() 函数，返回工具列表
5. **工具类型**：所有工具都是 RestfulApi 类型（除非明确需要 LocalFunction）

**输出格式要求（极其重要）**：
- 直接输出完整的 Python 代码
- 不要包含任何 markdown 代码块标记（如 ```python 或 ```）
- 不要包含任何 JSON 格式的数据
- 不要包含任何非代码的解释文字（解释信息应该作为 Python 注释）

请直接输出完整的 tools_analysis.py 的 Python 代码。"""
        
        # 调用 LLM 生成代码
        code = await llm_call_fn(prompt, system_prompt=system_content)
        
        # 清理代码（移除 markdown 代码块标记）
        code = self._clean_code(code)
        
        logger.info(f"✅ 使用 LLM 生成 tools_analysis.py 成功，代码长度: {len(code)} 字符")
        return code
    
    def _build_tools_info(self, tools: List[Dict[str, Any]]) -> str:
        """
        构建工具信息字符串（仅需求描述）
        
        Args:
            tools: 工具列表
        
        Returns:
            格式化的工具信息字符串
        """
        if not tools:
            return "工具总数: 0（不使用工具）\n"
        
        tools_info = f"工具总数: {len(tools)}\n"
        for idx, tool in enumerate(tools, 1):
            tools_info += f"\n工具 {idx}:\n"
            tools_info += f"- 名称: {tool.get('name', 'unknown')}\n"
            tools_info += f"- 描述: {tool.get('description', '无描述')}\n"
            
            # 可选字段（如果存在则显示）
            if tool.get('path'):
                tools_info += f"- 路径: {tool.get('path')}\n"
            if tool.get('method'):
                tools_info += f"- 方法: {tool.get('method')}\n"
            
            # 参数列表
            if tool.get('parameters'):
                tools_info += "- 参数列表:\n"
                tools_info += self._format_parameters(tool.get('parameters', {}))
        
        return tools_info
    
    def _format_tool_details(self, tool: Dict[str, Any]) -> str:
        """
        格式化单个工具的详细信息
        
        Args:
            tool: 工具字典（包含完整实现细节）
        
        Returns:
            格式化的工具信息字符串
        """
        details = f"- ID: {tool.get('id', 'unknown')}\n"
        details += f"- 名称: {tool.get('name', 'unknown')}\n"
        details += f"- 描述: {tool.get('description', '无描述')}\n"
        details += f"- 类别: {tool.get('category', '未分类')}\n"
        details += f"- 路径: {tool.get('path', '未指定')}\n"
        details += f"- 方法: {tool.get('method', '未指定')}\n"
        
        # Headers
        headers = tool.get('headers')
        if headers:
            headers_str = ", ".join([f"{k}: {v}" for k, v in headers.items()])
            details += f"- Headers: {{{headers_str}}}\n"
        
        # 参数信息
        params = tool.get('params', {})
        if params and 'properties' in params:
            details += "- 参数列表:\n"
            properties = params['properties']
            required = params.get('required', [])
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '无描述')
                is_required = param_name in required
                required_str = "必需" if is_required else "可选"
                details += f"  * {param_name} ({param_type}, {required_str}): {param_desc}\n"
        
        # 备注信息
        if tool.get('notes'):
            details += f"- 备注: {tool.get('notes')}\n"
        
        return details
    
    def _build_tools_info_with_details(
        self, 
        plan_tools: List[Dict[str, Any]], 
        available_tools: List[Dict[str, Any]]
    ) -> str:
        """
        构建工具信息字符串（包含完整实现细节）
        
        从可用工具列表中查找对应的工具，合并规划阶段的工具需求和实现细节
        
        Args:
            plan_tools: 规划阶段的工具列表（包含 name、description、parameters）
            available_tools: 可用工具列表（包含完整实现细节）
        
        Returns:
            格式化的工具信息字符串（包含完整实现细节）
        """
        if not plan_tools:
            return "工具总数: 0（不使用工具）\n"
        
        tools_info = f"工具总数: {len(plan_tools)}\n"
        
        for idx, plan_tool in enumerate(plan_tools, 1):
            tool_name = plan_tool.get('name', 'unknown')
            tools_info += f"\n工具 {idx}: {tool_name}\n"
            
            # 从可用工具列表中查找对应的工具
            matched_tool = get_tool_by_name(available_tools, tool_name)
            
            if matched_tool:
                tools_info += self._format_tool_details(matched_tool)
                logger.info(f"✅ 找到工具 {tool_name} 的完整实现细节（ID: {matched_tool.get('id')}）")
            else:
                # 如果找不到匹配的工具，使用规划阶段的工具信息（警告）
                logger.warning(f"⚠️ 未找到工具 {tool_name} 的完整实现细节，将使用规划阶段的描述")
                tools_info += f"- 描述: {plan_tool.get('description', '无描述')}\n"
                tools_info += f"- 警告: 此工具不在可用工具列表中，需要手动实现\n"
                
                # 参数列表（使用规划阶段的 parameters）
                if plan_tool.get('parameters'):
                    tools_info += "- 参数列表:\n"
                    tools_info += self._format_parameters(plan_tool.get('parameters', {}))
        
        return tools_info
    
    def _format_parameters(self, parameters: Dict[str, Any]) -> str:
        """
        格式化参数信息
        
        Args:
            parameters: 参数字典
        
        Returns:
            格式化的参数字符串
        """
        params_text = ""
        for param_name, param_info in parameters.items():
            if isinstance(param_info, dict):
                param_desc = param_info.get('description', '无描述')
                param_type = param_info.get('type', 'string')
                required = param_info.get('required', False)
                required_str = "必需" if required else "可选"
                params_text += f"  * {param_name} ({param_type}, {required_str}): {param_desc}\n"
            else:
                params_text += f"  * {param_name}: {param_info}\n"
        return params_text
    
    async def _generate_local_agent(self, plan: ReActPlan, context: Dict[str, Any]) -> str:
        """
        生成 local_agent.py
        
        使用 LLM 生成实际代码
        """
        # 获取 LLM 调用能力
        llm_call_fn = context.get("llm_call_fn")
        system_content = context.get("system_content", "")
        
        if not llm_call_fn or not system_content:
            raise ValueError("缺少 LLM 调用能力：context 中必须包含 'llm_call_fn' 和 'system_content'")
        
        logger.info("使用 LLM 生成 local_agent.py")
        return await self._generate_local_agent_with_llm(plan, context, llm_call_fn, system_content)
    
    async def _generate_local_agent_with_llm(
        self,
        plan: ReActPlan,
        context: Dict[str, Any],
        llm_call_fn: Callable,
        system_content: str
    ) -> str:
        """使用 LLM 生成 local_agent.py 的实际代码"""
        generated_files = context.get("generated_files", {})
        
        # 从 skill 读取 agent-generation.md（生成规则）
        skill_data = self.skill_manager.load_skill(self.skill_name)
        agent_generation_ref = ""
        if skill_data and "agent-generation.md" in skill_data.get("references", {}):
            agent_generation_ref = skill_data["references"]["agent-generation.md"]
            logger.info("✅ 已从 skill 读取 agent-generation.md 生成规则")
        else:
            logger.warning("⚠️ 无法从 skill 读取 agent-generation.md，将使用默认规则")
        
        # 获取已生成的文件完整内容（如果存在）
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
        
        if "tools_analysis.py" in generated_files:
            tools_code = generated_files["tools_analysis.py"]
            previous_files_section += f"""
**========== 已生成的 tools_analysis.py 完整内容（必须严格参考）==========**
```python
{tools_code}
```

**关键要求**：
1. 必须从 tools_analysis 导入工具函数
2. 必须使用 get_all_tools() 来获取工具，不要重新创建工具实例
3. 确保导入语句正确：`from tools_analysis import get_all_tools`
**========== tools_analysis.py 内容结束 ==========**

"""
        
        # 构建工具描述
        tools_description = ""
        if plan.tools:
            tools_description = "\n需要的工具：\n"
            for tool in plan.tools:
                tools_description += f"- {tool.get('name', 'unknown')}: {tool.get('description', '')}\n"
        
        # 构建 prompt（使用 skill 中的生成规则）
        prompt = f"""{system_content}

## 任务：生成 local_agent.py

根据以下信息生成完整的 local_agent.py 文件：

### Agent 信息
- Agent 名称：{plan.agent_description or 'react_agent'}
- Agent 描述：{plan.agent_description}
- 用户输入：{context.get('query', context.get('user_input', ''))}
- 系统提示词：{plan.system_prompt or '你是一个AI助手，在适当的时候调用合适的工具，帮助我完成任务！'}
{tools_description}

### 已生成的文件（必须严格参考）
以下是之前已生成的所有文件内容。在生成 local_agent.py 时，**必须**参考这些文件，确保：
- 导入的模块和函数名称与实际文件中的定义完全一致
- 使用的常量和配置与实际文件中的定义完全一致
- 函数调用方式和参数与实际文件的接口完全一致

{previous_files_section}

{agent_generation_ref}

**重要约束（必须严格遵守）**：
1. **只输出 Python 代码**：不要输出 JSON、markdown 注释或解释文字
2. **代码块标记**：不要使用 ```python 或 ``` 标记
3. **注释规范**：所有解释信息必须以 # 或 \"\"\" 形式作为 Python 注释
4. **必需函数**：必须包含 create_agent() 函数，返回 ReActAgent 实例

**输出格式要求（极其重要）**：
- 直接输出完整的 Python 代码
- 不要包含任何 markdown 代码块标记（如 ```python 或 ```）
- 不要包含任何 JSON 格式的数据
- 不要包含任何非代码的解释文字（解释信息应该作为 Python 注释）

请直接输出完整的 local_agent.py 的 Python 代码。"""
        
        # 调用 LLM 生成代码
        code = await llm_call_fn(prompt, system_prompt=system_content)
        
        # 清理代码（移除 markdown 代码块标记）
        code = self._clean_code(code)
        
        logger.info(f"✅ 使用 LLM 生成 local_agent.py 成功，代码长度: {len(code)} 字符")
        return code
    
    async def _generate_main(self, plan: ReActPlan, context: Dict[str, Any]) -> str:
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
        plan: ReActPlan,
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
        
        # 获取所有已生成文件的完整内容（按生成顺序：config.py、tools_analysis.py、local_agent.py）
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
        
        if "tools_analysis.py" in generated_files:
            tools_code = generated_files["tools_analysis.py"]
            previous_files_section += f"""
**========== 已生成的 tools_analysis.py 完整内容（必须严格参考）==========**
```python
{tools_code}
```
**========== tools_analysis.py 内容结束 ==========**

"""
        
        if "local_agent.py" in generated_files:
            local_agent_code = generated_files["local_agent.py"]
            previous_files_section += f"""
**========== 已生成的 local_agent.py 完整内容（必须严格参考）==========**
```python
{local_agent_code}
```

**关键要求**：
1. 必须从 local_agent 导入 create_agent 函数
2. 必须使用 create_agent() 来创建 Agent
3. 确保导入语句正确：`from local_agent import create_agent`
**========== local_agent.py 内容结束 ==========**

"""
        
        # 构建 prompt（使用 skill 中的生成规则）
        prompt = f"""{system_content}

## 任务：生成 main.py

根据以下信息生成完整的 main.py 文件：

### Agent 信息
- Agent 名称：{plan.agent_description or 'react_agent'}
- Agent 描述：{plan.agent_description}
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
4. **必需函数**：必须包含 run_test() 和 main() 函数

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
