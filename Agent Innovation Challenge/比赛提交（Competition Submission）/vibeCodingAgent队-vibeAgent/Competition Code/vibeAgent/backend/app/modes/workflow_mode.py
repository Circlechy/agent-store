"""
Workflow 模式生成器

生成 Workflow 代码
"""
from typing import Dict, Any, List, Optional, Callable
import re
from loguru import logger

from app.modes.base import ModeGenerator
from app.models.task import WorkflowPlan
from app.skills.skill_manager import SkillManager
from app.config.tools_config import load_available_tools

class WorkflowModeGenerator(ModeGenerator):
    """Workflow 模式生成器"""
    
    def __init__(self):
        """初始化 Workflow 模式生成器"""
        self.skill_manager = SkillManager()
        self.skill_name = "workflow-generation-skill"
    
    def get_required_files(self) -> List[str]:
        """获取必需的文件列表"""
        return ["config.py", "components.py", "workflow_builder.py", "main.py"]
    
    async def generate(self, plan: WorkflowPlan, context: Dict[str, Any] = None) -> Dict[str, str]:
        """生成 Workflow 代码"""
        if plan is None:
            raise ValueError("WorkflowPlan 不能为 None，请确保规划器成功生成计划")
        
        context = context or {}
        files = {}
        
        # 按顺序生成文件（使用基类的辅助方法）
        file_generators = [
            ("config.py", self._generate_config),
            ("components.py", self._generate_components),
            ("workflow_builder.py", self._generate_workflow_builder),
            ("main.py", self._generate_main),
        ]
        
        for file_name, generator_func in file_generators:
            context["generated_files"] = files  # 更新已生成文件供后续使用
            await self._generate_file_with_thinking(file_name, generator_func, plan, files, context)
        
        logger.info(f"生成 Workflow 代码: {len(files)} 个文件")
        return files
    
    async def _generate_config(self, plan: WorkflowPlan, context: Dict[str, Any]) -> str:
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
        plan: WorkflowPlan,
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
        system_prompt = config_generation_ref
        prompt = f"""根据以下信息生成完整的 config.py 文件：

### 工作流信息
- 工作流名称：{context.get('workflow_name', 'default')}
- 工作流描述：{plan.workflow_description}
- 用户输入：{context.get('query', context.get('user_input', ''))}

请直接输出完整的 config.py 的 Python 代码。"""
        
        # 调用 LLM 生成代码
        code = await llm_call_fn(prompt, system_prompt=system_prompt)
        
        # 清理代码（移除 markdown 代码块标记）
        code = self._clean_code(code)
        
        logger.info(f"✅ 使用 LLM 生成 config.py 成功，代码长度: {len(code)} 字符")
        return code
    
    async def _generate_components(self, plan: WorkflowPlan, context: Dict[str, Any]) -> str:
        """
        生成 components.py
        
        使用 LLM 生成实际代码
        """
        # 获取 LLM 调用能力
        llm_call_fn = context.get("llm_call_fn")
        system_content = context.get("system_content", "")
        
        if not llm_call_fn or not system_content:
            raise ValueError("缺少 LLM 调用能力：context 中必须包含 'llm_call_fn' 和 'system_content'")
        
        if not plan.components:
            raise ValueError("WorkflowPlan.components 不能为空，请确保规划器成功生成了组件列表。如果 components 为空，说明 PlannerAgent 的规划失败，请检查规划器的输出。")
        
        logger.info("使用 LLM 生成 components.py")
        return await self._generate_components_with_llm(plan, context, llm_call_fn, system_content)
    
    async def _generate_components_with_llm(
        self,
        plan: WorkflowPlan,
        context: Dict[str, Any],
        llm_call_fn: Callable,
        system_content: str
    ) -> str:
        """使用 LLM 生成 components.py 的实际代码"""
        generated_files = context.get("generated_files", {})
        
        # 构建组件信息列表
        components_info = []
        component_functions_list = []
        for c in plan.components:
            if isinstance(c, dict) and 'component_id' in c:
                comp_id = c['component_id']
                func_name = f"create_{comp_id}_component"
                components_info.append(
                    f"- {comp_id}: {c.get('component_name', comp_id)} "
                    f"({c.get('component_type', 'unknown')}) - {c.get('description', '')}"
                )
                component_functions_list.append(f"  {func_name}")
        
        components_info_str = "\n".join(components_info) if components_info else "- 无组件信息"
        component_functions_str = "\n".join(component_functions_list) if component_functions_list else "  （无组件函数）"
        
        logger.info(f"准备生成的组件函数列表: {component_functions_list}")
        
        # 从 skill 读取 component-generation.md（生成规则）
        skill_data = self.skill_manager.load_skill(self.skill_name)
        component_generation_ref = ""
        if skill_data and "component-generation.md" in skill_data.get("references", {}):
            component_generation_ref = skill_data["references"]["component-generation.md"]
            logger.info("✅ 已从 skill 读取 component-generation.md 生成规则")
        else:
            logger.warning("⚠️ 无法从 skill 读取 component-generation.md，将使用默认规则")
        
        tools_info_section = load_available_tools()
        # 构建 prompt（使用 skill 中的生成规则）
        system_prompt = component_generation_ref
        prompt = f"""## 用户输入
根据以下信息生成完整的 components.py 文件：

### 工作流信息
- 工作流名称：{context.get('workflow_name', 'default')}
- 工作流描述：{plan.workflow_description}
- 工作流创建指令：{context.get('query', context.get('user_input', ''))}

### 工作流组件列表及连接信息
需要的组件：
{components_info_str}

### 关键要求：必须生成以下所有组件创建函数（函数名必须完全匹配，不能遗漏任何函数）
{component_functions_str}

### 可用外部工具（ToolComponent生成时使用）
{tools_info_section}
如果需要使用ToolComponent，请从可用工具信息中选择合适工具，实现ToolComponent组件。

请直接输出完整的 components.py 的 Python 代码，确保所有函数名完全匹配。"""
        
        # 调用 LLM 生成代码
        code = await llm_call_fn(prompt, system_prompt=system_prompt)
        
        # 清理代码（移除 markdown 代码块标记）
        code = self._clean_code(code)
        
        logger.info(f"✅ 使用 LLM 生成 components.py 成功，代码长度: {len(code)} 字符")
        return code
    
    def _clean_code(self, code: str) -> str:
        """
        清理生成的代码并验证语法
        
        Args:
            code: 原始代码
        
        Returns:
            清理后的代码
        """
        # 移除 markdown 代码块标记
        code = re.sub(r'^```python\s*\n', '', code, flags=re.MULTILINE)
        code = re.sub(r'^```\s*\n', '', code, flags=re.MULTILINE)
        code = re.sub(r'```$', '', code, flags=re.MULTILINE)
        code = code.strip()
        
        # 验证语法
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            logger.warning(f"生成的代码存在语法错误: {e}")
            logger.warning(f"错误位置: 第 {e.lineno} 行，列 {e.offset}")
            logger.warning(f"错误代码片段: {e.text}")
            # 不抛出异常，返回错误代码，让调用者处理
        
        return code
    
    async def _generate_workflow_builder(self, plan: WorkflowPlan, context: Dict[str, Any]) -> str:
        """
        生成 workflow_builder.py
        
        使用 LLM 生成实际代码
        """
        # 获取 LLM 调用能力
        llm_call_fn = context.get("llm_call_fn")
        system_content = context.get("system_content", "")
        
        if not llm_call_fn or not system_content:
            raise ValueError("缺少 LLM 调用能力：context 中必须包含 'llm_call_fn' 和 'system_content'")
        
        logger.info("使用 LLM 生成 workflow_builder.py")
        return await self._generate_workflow_builder_with_llm(plan, context, llm_call_fn, system_content)
    
    async def _generate_workflow_builder_with_llm(
        self,
        plan: WorkflowPlan,
        context: Dict[str, Any],
        llm_call_fn: Callable,
        system_content: str
    ) -> str:
        """使用 LLM 生成 workflow_builder.py 的实际代码"""
        generated_files = context.get("generated_files", {})
        
        # 从 skill 读取 workflow-builder-generation.md（生成规则）
        skill_data = self.skill_manager.load_skill(self.skill_name)
        workflow_builder_generation_ref = ""
        if skill_data and "workflow-builder-generation.md" in skill_data.get("references", {}):
            workflow_builder_generation_ref = skill_data["references"]["workflow-builder-generation.md"]
            logger.info("✅ 已从 skill 读取 workflow-builder-generation.md 生成规则")
        else:
            logger.warning("⚠️ 无法从 skill 读取 workflow-builder-generation.md，将使用默认规则")
        
        # 获取所有已生成文件的完整内容（按生成顺序：config.py、components.py）
        previous_files_section = ""
        
        if "components.py" in generated_files:
            components_code = generated_files["components.py"]
            previous_files_section += f"""**========== 已生成的 components.py 完整内容（必须严格参考）==========**
```python
{components_code}
```
**========== components.py 内容结束 ==========**"""
        
        # 从 components.py 中提取组件函数列表
        component_functions = []
        if "components.py" in generated_files:
            components_code = generated_files["components.py"]
            pattern = r'def\s+(create_\w+_component)\s*\('
            found_functions = re.findall(pattern, components_code)
            if found_functions:
                component_functions = found_functions
                logger.info(f"从 components.py 中提取到 {len(component_functions)} 个函数: {component_functions}")
        
        # 构建导入语句示例
        import_example = "from components import (\n"
        for func in component_functions:
            import_example += f"    {func},\n"
        import_example += ")"

        # 构建组件信息列表，明确列出每个组件应该生成的函数名
        used_tools_name_list = []
        for c in plan.components:
            if isinstance(c, dict) and 'component_id' in c:
                comp_id = c['component_id']
                if c.get('component_type', 'unknown') == 'ToolComponent':
                    used_tools_name_list.append(c.get('component_name', comp_id))
        if used_tools_name_list:
            logger.info(f"准备使用的工具列表: {used_tools_name_list}")
        tools_info_list = load_available_tools()
        tools_info_section = ""
        for tool in tools_info_list:
            if tool.get('name') in used_tools_name_list:
                tools_info_section += (f"- {tool.get('name')}: {tool.get('description')}\n"
                f"inputs: {tool.get('params')}\n"   
                f"outputs: {tool.get('response')}\n"
                )
        if tools_info_section:
            logger.info(f"准备使用的工具信息:\n {tools_info_section}")
        

        # 构建 prompt（使用 skill 中的生成规则）
        reference_code = self.skill_manager.load_references_code(self.skill_name, ["config_file_reference.py", "components.py", "generate_workflow_builder_reference.py"])
        system_prompt = workflow_builder_generation_ref + f"""\n## 示例代码及相应说明（必须严格参考）
示例代码给出了config.py和components.py的示例代码，以及workflow_builder.py的示例代码，请严格参考示例代码，生成具体的workflow_builder.py的代码。
<python_code>
{reference_code}
</python_code>
        """

        prompt = f"""## 用户输入

根据以下信息生成完整的 workflow_builder.py 文件：

### 工作流信息
- 工作流名称：{context.get('workflow_name', 'default')}
- 工作流描述：{plan.workflow_description}
- 工作流创建指令：{context.get('query', context.get('user_input', ''))}

### 组件列表
组件函数列表：
{import_example}

### 已生成的components.py内容（必须严格参考）
{previous_files_section}

### 可用外部工具：
{tools_info_section}
根据外部工具的具体信息：
1. 确定每个ToolComponent的inputs_schema，确保字段名完全一致。
2. 当其他组件引用ToolComponent的输出时，确保引用字段名与ToolComponent的outputs中的字段名一致。

请直接输出完整的 workflow_builder.py 的 Python 代码。"""
        
        # 调用 LLM 生成代码
        code = await llm_call_fn(prompt, system_prompt=system_prompt)
        
        # 清理代码（移除 markdown 代码块标记）
        code = self._clean_code(code)
        
        logger.info(f"✅ 使用 LLM 生成 workflow_builder.py 成功，代码长度: {len(code)} 字符")
        return code
    
    async def _generate_main(self, plan: WorkflowPlan, context: Dict[str, Any]) -> str:
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
        plan: WorkflowPlan,
        context: Dict[str, Any],
        llm_call_fn: Callable,
        system_content: str
    ) -> str:
        """使用 LLM 生成 main.py 的实际代码"""
        generated_files = context.get("generated_files", {})
        
        # 从 skill 读取 main-generation.md（生成规则）
        # 自动检测文件更新，如果文件已修改则重新加载
        force_reload = context.get("force_reload_skill", False)
        skill_data = self.skill_manager.load_skill(self.skill_name, force_reload=force_reload)
        main_generation_ref = ""
        if skill_data and "main-generation.md" in skill_data.get("references", {}):
            main_generation_ref = skill_data["references"]["main-generation.md"]
            logger.info("✅ 已从 skill 读取 main-generation.md 生成规则")
            # 调试：打印前 500 字符验证内容
            logger.debug(f"main-generation.md 前 500 字符: {main_generation_ref[:500]}")
        else:
            logger.warning("⚠️ 无法从 skill 读取 main-generation.md，将使用默认规则")
            if skill_data:
                logger.warning(f"可用的 references: {list(skill_data.get('references', {}).keys())}")
        
        # 获取所有已生成文件的完整内容（按生成顺序：config.py、components.py、workflow_builder.py）
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
        
        if "components.py" in generated_files:
            components_code = generated_files["components.py"]
            previous_files_section += f"""
**========== 已生成的 components.py 完整内容（必须严格参考）==========**
```python
{components_code}
```
**========== components.py 内容结束 ==========**

"""
        
        if "workflow_builder.py" in generated_files:
            workflow_builder_code = generated_files["workflow_builder.py"]
            previous_files_section += f"""
**========== 已生成的 workflow_builder.py 完整内容（必须严格参考）==========**
以下是已经生成的 workflow_builder.py 文件的完整内容。在生成 main.py 时，**必须**使用这个文件中定义的 build_workflow_agent() 函数。

```python
{workflow_builder_code}
```

**关键要求**：
1. 必须从 workflow_builder 导入 build_workflow_agent 函数
2. 必须使用 build_workflow_agent() 来构建工作流 Agent
3. 确保导入语句正确：`from workflow_builder import build_workflow_agent`
**========== workflow_builder.py 内容结束 ==========**
"""
        
        # 构建 prompt（使用 skill 中的生成规则）
        reference_code = self.skill_manager.load_references_code(self.skill_name, ["generate_main_file_reference.py"])
        system_prompt = main_generation_ref + f"""\n## 示例代码及相应说明（必须严格参考）
示例代码给出了main.py的示例代码，请严格参考示例代码，生成具体的main.py的代码。
<python_code>
{reference_code}
</python_code>
"""
        prompt = f"""## 任务：生成 main.py

根据以下信息生成完整的 main.py 文件：

### 工作流信息
- 工作流名称：{context.get('workflow_name', 'default')}
- 工作流描述：{plan.workflow_description}
- 用户输入：{context.get('query', context.get('user_input', ''))}

### 已生成的文件（必须严格参考）
以下是之前已生成的所有文件内容。在生成 main.py 时，**必须**参考这些文件，确保：
- 导入的模块和函数名称与实际文件中的定义完全一致
- 使用的常量和配置与实际文件中的定义完全一致
- 函数调用方式和参数与实际文件的接口完全一致

{previous_files_section}

**重要约束（必须严格遵守）**：
1. **只输出 Python 代码**：不要输出 JSON、markdown 注释或解释文字
2. **代码块标记**：不要使用 ```python 或 ``` 标记
3. **注释规范**：所有解释信息必须以 # 或 \"\"\" 形式作为 Python 注释
4. **导入顺序**：**必须**在最前面导入 `import setup_path`，必须在所有 openjiuwen 相关模块导入之前
5. **编码设置**：**必须**在导入语句后设置 UTF-8 编码（避免 Windows GBK 编码错误）：`if sys.platform == "win32": sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')`
6. **必需函数**：必须包含 run_test() 和 main() 函数
7. **环境变量**：必须设置 WORKFLOW_EXECUTE_TIMEOUT 环境变量
8. **导入完整**：必须从 workflow_builder 导入 build_workflow_agent

**输出格式要求（极其重要）**：
- 直接输出完整的 Python 代码
- 不要包含任何 markdown 代码块标记（如 ```python 或 ```）
- 不要包含任何 JSON 格式的数据
- 不要包含任何非代码的解释文字（解释信息应该作为 Python 注释）

请直接输出完整的 main.py 的 Python 代码。"""

        # print(f"*** workflow_mode.py prompt: {prompt}")
        
        # 调用 LLM 生成代码
        code = await llm_call_fn(prompt, system_prompt=system_prompt)
        # print(f"*** workflow_mode.py code: {code}")
        
        # 清理代码（移除 markdown 代码块标记）
        code = self._clean_code(code)
        
        logger.info(f"✅ 使用 LLM 生成 main.py 成功，代码长度: {len(code)} 字符")
        return code
