"""
修复 Agent（FixerAgent）

负责修复代码错误和工作流修改
"""
import asyncio
import json
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional, AsyncIterator, List

from loguru import logger
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.agent.config.base import AgentConfig

from app.agents.base import VibeBaseAgent
from app.context.context_manager import ContextManager
from app.session.session_manager import SessionManager
from app.skills.skill_manager import SkillManager
from app.models.agent_result import AgentResult


class FixerAgent(VibeBaseAgent):
    """
    修复 Agent - 继承 openJiuwen.BaseAgent
    
    职责：修复代码错误
    关键约束：
    - ❌ 禁止使用 delegate_task 工具
    - ✅ 可以使用其他所有工具
    """
    
    def __init__(
        self,
        agent_config: AgentConfig,
        context_manager: Optional[ContextManager] = None,
        session_manager: Optional[SessionManager] = None,
        skill_manager: Optional[SkillManager] = None
    ):
        """
        初始化修复 Agent
        
        Args:
            agent_config: Agent 配置（必须包含 model）
            context_manager: 上下文管理器
            session_manager: 会话管理器（用于获取会话历史）
            skill_manager: 技能管理器（用于读取技能内容）
        """
        super().__init__(agent_config, context_manager)
        self.session_manager = session_manager
        self.skill_manager = skill_manager or SkillManager()
        logger.info("初始化 FixerAgent")
    
    async def invoke(self, inputs: Dict, runtime: Runtime = None) -> Dict:
        """
        实现 openJiuwen 的 invoke 接口
        
        Args:
            inputs: 输入数据，包含 task_type 和其他任务特定参数
            runtime: Runtime 实例
        
        Returns:
            执行结果
        """
        try:
            task_type = inputs.get("task_type")
            
            if task_type == "analyze_and_modify":
                return await self._handle_analyze_and_modify(inputs, runtime)
            elif task_type == "analyze_modification":
                return await self._handle_analyze_modification(inputs, runtime)
            elif task_type == "modify_file":
                return await self._handle_modify_file(inputs, runtime)
            elif task_type == "fix_errors":
                return await self._handle_fix_errors(inputs, runtime)
            else:
                # 兼容旧版本的 fix 任务类型
                return await self._handle_fix_errors(inputs, runtime)
        
        except Exception as e:
            logger.error(f"执行失败: {e}", exc_info=True)
            return AgentResult.failure_result(error=str(e)).to_dict()
    
    async def _handle_analyze_and_modify(self, inputs: Dict, runtime: Runtime) -> Dict:
        """处理分析并修改任务"""
        result = await self.analyze_and_modify(
            workflow_dir=inputs.get("workflow_dir", ""),
            modification_request=inputs.get("modification_request", ""),
            conversation_id=inputs.get("conversation_id"),
            event_queue=inputs.get("_event_queue"),
            runtime=runtime
        )
        return AgentResult.success_result(data=result).to_dict()
    
    async def _handle_analyze_modification(self, inputs: Dict, runtime: Runtime) -> Dict:
        """处理分析修改任务（兼容模式）"""
        result = await self.analyze_modification(
            workflow_dir=inputs.get("workflow_dir", ""),
            modification_request=inputs.get("modification_request", ""),
            conversation_id=inputs.get("conversation_id")
        )
        return AgentResult.success_result(data=result).to_dict()
    
    async def _handle_modify_file(self, inputs: Dict, runtime: Runtime) -> Dict:
        """处理修改文件任务"""
        # 提取参数
        file_path = inputs.get("file_path", "")
        file_content = inputs.get("file_content", "")
        modification_request = inputs.get("modification_request", "")
        all_requirements = inputs.get("all_requirements", [])
        all_files = inputs.get("all_files", {})
        components = inputs.get("components")
        workflow_structure = inputs.get("workflow_structure")
        event_queue = inputs.get("_event_queue")
        
        # 验证参数
        validation_error = self._validate_modify_file_params(
            file_path, file_content, modification_request, all_requirements
        )
        if validation_error:
            return AgentResult.failure_result(error=validation_error).to_dict()
        
        # 规范化 all_requirements
        if not all_requirements:
            all_requirements = [modification_request] if modification_request else []
        
        logger.debug(f"修改文件: {file_path}, 需求数: {len(all_requirements)}, "
                    f"组件数: {len(components) if components else 0}")
        
        result = await self.modify_file(
            file_path=file_path,
            file_content=file_content,
            modification_request=modification_request,
            all_requirements=all_requirements,
            all_files=all_files,
            event_queue=event_queue,
            runtime=runtime,
            components=components,
            workflow_structure=workflow_structure
        )
        return AgentResult.success_result(data=result).to_dict()
    
    async def _handle_fix_errors(self, inputs: Dict, runtime: Runtime) -> Dict:
        """
        处理修复代码错误任务（场景2）
        
        复用 analyze_and_modify 的逻辑，将错误信息转换为修改需求
        """
        error_info = inputs.get("error_info", {})
        workflow_dir = inputs.get("workflow_dir", "")
        files = inputs.get("files", {})
        event_queue = inputs.get("_event_queue")
        
        # 将错误信息转换为修改需求
        modification_request = self._build_modification_request_from_errors(error_info)
        
        # 复用 analyze_and_modify 的逻辑
        result = await self.analyze_and_modify(
            workflow_dir=workflow_dir,
            modification_request=modification_request,
            conversation_id=None,  # 修复场景不需要历史
            event_queue=event_queue,
            runtime=runtime
        )
        
        # 转换返回格式（保持兼容性）
        return AgentResult.success_result(data=result).to_dict()
    
    def _validate_modify_file_params(
        self, file_path: str, file_content: str, 
        modification_request: str, all_requirements: List[str]
    ) -> Optional[str]:
        """验证修改文件参数"""
        if not file_path:
            return "file_path 不能为空"
        if not file_content:
            return f"file_content 不能为空（文件: {file_path}）"
        return None
    
    async def stream(self, inputs: Dict, runtime: Runtime = None) -> AsyncIterator[Any]:
        """实现 openJiuwen 的 stream 接口"""
        result = await self.invoke(inputs, runtime)
        yield result
    
    async def _fix_errors(
        self,
        error_info: Dict[str, Any],
        workflow_dir: str,
        files: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        修复代码错误
        
        Args:
            error_info: 错误信息 {test_output, errors, failed_tests}
            workflow_dir: 工作流目录
            files: 当前文件内容
        
        Returns:
            修复结果
        """
        # 构建修复提示词
        prompt = self._build_fix_prompt(error_info, files)
        system_prompt = self._get_system_prompt()
        
        # 调用 LLM 生成修复方案
        response = await self._call_llm(prompt, system_prompt=system_prompt, runtime=self._runtime)
        
        # 解析响应，提取修复后的代码
        fixed_files = self._parse_fix_response(response, files)
        
        return {
            "fixed": len(fixed_files) > 0,
            "fixed_files": fixed_files,
            "remaining_errors": []
        }
    
    def _build_fix_prompt(self, error_info: Dict[str, Any], files: Dict[str, str]) -> str:
        """构建修复提示词"""
        prompt_parts = [
            "## 错误信息",
            f"测试输出: {error_info.get('test_output', '')}",
            f"错误: {error_info.get('errors', '')}",
            "",
            "## 当前代码",
        ]
        
        for filename, content in files.items():
            prompt_parts.extend([
                f"### {filename}",
                "```python",
                content[:2000],  # 限制长度
                "```",
                ""
            ])
        
        prompt_parts.extend([
            "## 要求",
            "请分析错误原因，修复代码中的问题。",
            "只输出修复后的代码，使用 ```python 代码块包裹。",
            "如果涉及多个文件，请为每个文件单独输出代码块。"
        ])
        
        return "\n".join(prompt_parts)
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的代码修复专家。
你的任务是分析错误信息，定位问题，并生成修复后的代码。

要求：
1. 仔细分析错误信息，准确定位问题
2. 修复后的代码必须符合 openJiuwen 框架规范
3. 保持代码风格一致
4. 确保修复后的代码可以正常运行"""
    
    def _parse_fix_response(self, response: str, original_files: Dict[str, str]) -> Dict[str, str]:
        """解析修复响应，提取修复后的代码"""
        fixed_files = {}
        pattern = r'```python\s*\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        if matches:
            file_list = list(original_files.keys())
            for i, code in enumerate(matches):
                filename = self._infer_filename(code, original_files) or (
                    file_list[i] if i < len(file_list) else None
                )
                if filename:
                    fixed_files[filename] = code.strip()
        elif original_files:
            # 如果没有代码块，假设修复第一个文件
            first_file = list(original_files.keys())[0]
            fixed_files[first_file] = response.strip()
        
        return fixed_files
    
    def _infer_filename(self, code: str, original_files: Dict[str, str]) -> Optional[str]:
        """从代码中推断文件名（通过类名匹配）"""
        class_match = re.search(r'class\s+(\w+)', code)
        if class_match:
            class_name = class_match.group(1).lower()
            for filename in original_files.keys():
                if class_name in filename.lower():
                    return filename
        return None
    
    async def analyze_and_modify(
        self,
        workflow_dir: str,
        modification_request: str,
        conversation_id: Optional[str] = None,
        event_queue: Optional[asyncio.Queue] = None,
        runtime: Runtime = None
    ) -> Dict[str, Any]:
        """
        分析修改需求并修改所有文件（合并分析和修改流程）
        
        Args:
            workflow_dir: 工作流目录
            modification_request: 当前修改需求
            conversation_id: 会话ID（用于获取历史需求）
            event_queue: 事件队列（用于发送步骤事件和思考过程）
            runtime: Runtime 实例
        
        Returns:
            修改结果，包含 files_to_modify, modified_files, components, workflow_structure 等
        """
        # 1. 执行分析（内部会发送思考过程）
        if event_queue:
            await self._send_step_event(event_queue, "analyze_modification", "分析修改需求", 
                                      "分析修改需求，确定需要修改的文件", "started")
        
        analysis_result = await self.analyze_modification(
            workflow_dir=workflow_dir,
            modification_request=modification_request,
            conversation_id=conversation_id,
            event_queue=event_queue,
            runtime=runtime
        )
        
        files_to_modify = analysis_result.get("files_to_modify", [])
        modification_plan = analysis_result.get("modification_plan", {})
        all_files = analysis_result.get("all_files", {})
        all_requirements = analysis_result.get("all_requirements", [])
        components = analysis_result.get("components", [])
        workflow_structure = analysis_result.get("workflow_structure", {})
        
        # 验证 all_files 是否包含所有文件
        logger.info(f"📋 分析结果: files_to_modify={files_to_modify}, all_files包含={sorted(all_files.keys())}")
        
        # 如果 all_files 不完整，重新读取所有文件
        workflow_path = Path(workflow_dir)
        all_py_files = {f.name for f in workflow_path.glob("*.py")}
        missing_files = all_py_files - set(all_files.keys())
        if missing_files:
            logger.warning(f"⚠️ all_files 缺少文件: {missing_files}，正在补充...")
            for py_file in workflow_path.glob("*.py"):
                if py_file.name not in all_files:
                    try:
                        content = py_file.read_text(encoding="utf-8")
                        all_files[py_file.name] = content
                        logger.info(f"✅ 补充文件到 all_files: {py_file.name}")
                    except Exception as e:
                        logger.warning(f"⚠️ 读取文件失败 {py_file.name}: {e}")
        
        if event_queue:
            await self._send_step_event(
                event_queue, "analyze_modification", "分析修改需求",
                f"分析完成，需要修改 {len(files_to_modify)} 个文件", "completed",
                {"files_to_modify": files_to_modify, "modification_plan": modification_plan}
            )
        
        # 2. 修改所有文件
        modified_files = {}
        for file_name in files_to_modify:
            if file_name not in all_files:
                logger.warning(f"⚠️ 文件 {file_name} 不存在于 all_files 中，跳过")
                continue
            
            file_step_id = f"modify_{file_name.replace('.', '_')}"
            file_step_name = f"修改 {file_name}"
            description = modification_plan.get(file_name, f"修改 {file_name}")
            
            if event_queue:
                await self._send_step_event(
                    event_queue, file_step_id, file_step_name, description, "started",
                    step_type="modify_file"
                )
            
            try:
                modify_result = await self.modify_file(
                    file_path=file_name,
                    file_content=all_files[file_name],
                    modification_request=modification_request,
                    all_requirements=all_requirements,
                    all_files=all_files,
                    event_queue=event_queue,
                    runtime=runtime,
                    components=components,
                    workflow_structure=workflow_structure
                )
                
                modified_content = modify_result.get("modified_content", "")
                if modified_content:
                    modified_files[file_name] = modified_content
                    # 更新 all_files 中的文件内容（确保后续步骤能获取最新内容）
                    all_files[file_name] = modified_content
                
                if event_queue:
                    await self._send_step_event(
                        event_queue, file_step_id, file_step_name, description, "completed",
                        step_type="modify_file"
                    )
            except Exception as e:
                logger.error(f"❌ 修改文件 {file_name} 失败: {e}", exc_info=True)
                if event_queue:
                    await self._send_step_event(
                        event_queue, file_step_id, file_step_name, description, "completed",
                        step_type="modify_file", error=str(e)
                    )
        
        # 确保 all_files 包含所有文件（包括未修改的文件如 config.py、main.py 等）
        # 重新读取工作流目录，确保包含所有文件的最新内容
        workflow_path = Path(workflow_dir)
        all_py_files = list(workflow_path.glob("*.py"))
        logger.info(f"📁 工作流目录中共有 {len(all_py_files)} 个 Python 文件")
        
        for py_file in all_py_files:
            if py_file.name not in all_files:
                try:
                    content = py_file.read_text(encoding="utf-8")
                    all_files[py_file.name] = content
                    logger.info(f"✅ 补充文件到 all_files: {py_file.name} ({len(content)} 字符)")
                except Exception as e:
                    logger.warning(f"⚠️ 读取文件失败 {py_file.name}: {e}")
            else:
                logger.debug(f"✓ 文件已在 all_files 中: {py_file.name}")
        
        logger.info(f"✅ all_files 最终包含 {len(all_files)} 个文件: {sorted(all_files.keys())}")
        
        return {
            "files_to_modify": files_to_modify,
            "modified_files": modified_files,
            "modification_plan": modification_plan,
            "all_files": all_files,  # 包含所有文件（修改后的和未修改的）
            "all_requirements": all_requirements,
            "components": components,
            "workflow_structure": workflow_structure
        }
    
    async def _send_step_event(
        self,
        event_queue: asyncio.Queue,
        step_id: str,
        step_name: str,
        description: str,
        status: str,
        result_data: Optional[Dict] = None,
        step_type: Optional[str] = None,
        error: Optional[str] = None
    ):
        """发送步骤事件到事件队列"""
        event = {
            "type": f"step_{status}",
            "step_id": step_id,
            "step_name": step_name,
            "message": f"{'开始执行' if status == 'started' else '完成'}: {step_name}",
            "data": {
                "step": {
                    "step_id": step_id,
                    "step_name": step_name,
                    "step_type": step_type or step_id.split("_")[0],
                    "description": description
                }
            },
            "timestamp": time.time()
        }
        
        if result_data:
            event["data"]["result"] = result_data
        if error:
            event["data"]["error"] = error
            event["message"] = f"失败: {step_name}"
        
        await event_queue.put(event)
    
    async def analyze_modification(
        self,
        workflow_dir: str,
        modification_request: str,
        conversation_id: Optional[str] = None,
        event_queue: Optional[asyncio.Queue] = None,
        runtime: Runtime = None
    ) -> Dict[str, Any]:
        """
        分析修改需求，确定需要修改的文件
        
        Args:
            workflow_dir: 工作流目录
            modification_request: 当前修改需求
            conversation_id: 会话ID（用于获取历史需求）
            event_queue: 事件队列（用于发送思考过程）
            runtime: Runtime 实例
        
        Returns:
            分析结果 {files_to_modify: List[str], modification_plan: Dict[str, str]}
        """
        # 1. 读取所有工作流文件
        workflow_path = Path(workflow_dir)
        if not workflow_path.exists():
            raise ValueError(f"工作流目录不存在: {workflow_dir}")
        
        files = {}
        for py_file in workflow_path.glob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                files[py_file.name] = content
            except Exception as e:
                logger.warning(f"读取文件失败 {py_file.name}: {e}")
        
        if not files:
            raise ValueError(f"工作流目录中没有找到 Python 文件: {workflow_dir}")
        
        # 2. 获取会话历史（所有用户需求）
        all_requirements = [modification_request]  # 包含当前需求
        if conversation_id and self.session_manager:
            try:
                history = self.session_manager.get_conversation_history(conversation_id)
                if history:
                    # 将历史需求添加到列表前面（初始需求在前）
                    all_requirements = history + all_requirements
                    logger.info(f"获取到 {len(history)} 条历史需求")
            except Exception as e:
                logger.warning(f"获取会话历史失败: {e}，仅使用当前需求")
        
        # 3. 生成思考过程（如果提供了 event_queue）
        thinking_context = None
        if event_queue:
            thinking_prompt = self._build_thinking_prompt_for_analysis(
                modification_request=modification_request,
                all_requirements=all_requirements,
                files=files
            )
            thinking_system_prompt = """你是一位资深程序员，用口语化的方式表达思考。像在心里嘀咕一样，简短有力，不要书面化。"""
            
            step_id = "analyze_modification"
            step_name = "分析修改需求"
            
            thinking_context = await self._generate_thinking_stream(
                thinking_prompt=thinking_prompt,
                system_prompt=thinking_system_prompt,
                event_queue=event_queue,
                step_id=step_id,
                step_name=step_name,
                runtime=runtime
            )
        
        # 4. 构建分析提示词
        prompt = self._build_analysis_prompt(
            modification_request=modification_request,
            all_requirements=all_requirements,
            files=files,
            thinking_context=thinking_context
        )
        system_prompt = self._get_analysis_system_prompt()
        
        # 5. 调用 LLM 分析
        response = await self._call_llm(prompt, system_prompt=system_prompt, runtime=runtime or self._runtime)
        
        # 6. 解析响应，提取需要修改的文件列表
        result = self._parse_analysis_response(response, list(files.keys()))
        
        # 7. 添加 all_files 和 all_requirements 到返回结果
        result["all_files"] = files
        result["all_requirements"] = all_requirements
        
        return result
    
    async def modify_file(
        self,
        file_path: str,
        file_content: str,
        modification_request: str,
        all_requirements: List[str],
        all_files: Dict[str, str],
        event_queue: Optional[asyncio.Queue] = None,
        runtime: Runtime = None,
        components: Optional[List[Dict[str, Any]]] = None,
        workflow_structure: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        修改单个文件
        
        Args:
            file_path: 文件路径（相对路径，如 "config.py"）
            file_content: 文件当前内容
            modification_request: 当前修改需求
            all_requirements: 所有需求（初始需求 + 各轮修改需求）
            all_files: 所有文件（作为上下文）
            event_queue: 事件队列（用于发送思考过程）
            runtime: Runtime 实例
        
        Returns:
            修改结果 {modified_content: str, file_path: str}
        """
        # 1. 生成思考过程（如果提供了 event_queue）
        thinking_context = None
        if event_queue:
            thinking_prompt = self._build_thinking_prompt_for_modify(
                file_path=file_path,
                modification_request=modification_request,
                all_requirements=all_requirements,
                all_files=all_files,
                components=components,
                workflow_structure=workflow_structure
            )
            thinking_system_prompt = """你是一位资深程序员，用口语化的方式表达思考。像在心里嘀咕一样，简短有力，不要书面化。"""
            
            step_id = f"modify_{file_path.replace('.', '_')}"
            step_name = f"修改 {file_path}"
            
            thinking_context = await self._generate_thinking_stream(
                thinking_prompt=thinking_prompt,
                system_prompt=thinking_system_prompt,
                event_queue=event_queue,
                step_id=step_id,
                step_name=step_name,
                runtime=runtime
            )
        
        # 2. 构建修改提示词
        prompt = self._build_modify_prompt(
            file_path=file_path,
            file_content=file_content,
            modification_request=modification_request,
            all_requirements=all_requirements,
            all_files=all_files,
            thinking_context=thinking_context,
            components=components,
            workflow_structure=workflow_structure
        )
        system_prompt = self._get_modify_system_prompt()
        
        # 3. 调用 LLM 生成修改后的代码
        response = await self._call_llm(prompt, system_prompt=system_prompt, runtime=runtime)
        
        # 4. 解析响应，提取修改后的代码
        modified_content = self._parse_modify_response(response, file_content)
        
        return {
            "modified_content": modified_content,
            "file_path": file_path
        }
    
    def _build_analysis_prompt(
        self,
        modification_request: str,
        all_requirements: List[str],
        files: Dict[str, str],
        thinking_context: Optional[str] = None
    ) -> str:
        """构建分析提示词 - 参考 workflow-modification-guide.md 生成工作流结构"""
        is_workflow = "workflow_builder.py" in files or "components.py" in files
        
        prompt_parts = []
        
        # 如果有思考过程，添加到前面
        if thinking_context:
            prompt_parts.extend([
                "## Agent 思考过程",
                thinking_context,
                "",
                "---",
                ""
            ])
        
        prompt_parts.extend([
            "## 修改需求",
            f"当前需求: {modification_request}",
            "",
            "## 历史需求",
        ])
        
        # 添加历史需求（除了最后一个，即当前需求）
        for i, req in enumerate(all_requirements[:-1], 1):
            prompt_parts.append(f"{i}. {req}")
        
        prompt_parts.extend(["", "## 当前工作流文件"])
        
        # 显示所有文件的完整内容（不能只显示部分）
        for filename in sorted(files.keys()):
            content = files[filename]
            prompt_parts.extend([
                f"### {filename}",
                "```python",
                content,  # 显示完整内容，不截断
                "```",
                ""
            ])
        
        # 根据模式添加不同的任务说明
        if is_workflow:
            modification_guide = self._load_modification_guide()
            prompt_parts.extend(self._build_workflow_analysis_instructions(modification_guide))
        else:
            prompt_parts.extend(self._build_generic_analysis_instructions())
        
        return "\n".join(prompt_parts)
    
    def _load_modification_guide(self) -> str:
        """加载工作流修改指南"""
        skills_dir = Path(__file__).parent.parent.parent / "skills"
        guide_path = skills_dir / "workflow-fix-skill" / "references" / "workflow-modification-guide.md"
        
        if guide_path.exists():
            logger.info(f"✅ 加载工作流修改指南: {guide_path}")
            return guide_path.read_text(encoding="utf-8")
        else:
            logger.warning(f"⚠️ 工作流修改指南不存在: {guide_path}")
            return ""
    
    def _load_framework_rules(self) -> str:
        """加载框架规范文档"""
        skills_dir = Path(__file__).parent.parent.parent / "skills"
        rules_path = skills_dir / "workflow-fix-skill" / "references" / "framework-rules.md"
        
        if rules_path.exists():
            logger.info(f"✅ 加载框架规范: {rules_path}")
            return rules_path.read_text(encoding="utf-8")
        else:
            logger.warning(f"⚠️ 框架规范不存在: {rules_path}")
            return ""
    
    def _build_workflow_analysis_instructions(self, modification_guide: str) -> List[str]:
        """构建工作流模式的分析指令"""
        return [
            "",
            "## 任务",
            "分析上述所有需求（历史需求 + 当前需求），生成新的工作流结构。",
            "",
            "**重要原则**：",
            "1. **必须通过修改工作流拓扑结构来满足需求**，而不是在 component 文件中添加普通函数",
            "2. **如果需求是增加新功能，应该添加新的组件节点，然后重新连接拓扑**",
            "3. **如果需求是修改现有功能，应该修改对应组件的描述和配置**",
            "4. **必须保留现有组件**：如果现有组件仍然需要，必须在新的 `components` 列表中保留它们",
            "",
            "## 工作流修改指南",
            modification_guide if modification_guide else "请参考工作流修改指南进行修改",
            "",
            "## 输出格式（JSON）",
            "必须包含以下字段：",
            '{"files_to_modify": ["file1.py", "file2.py"], "modification_plan": {"file1.py": "修改说明1", "file2.py": "修改说明2"}, "components": [...], "workflow_structure": {...}}',
            "",
            "**关键字段说明**：",
            "- `files_to_modify`: 需要修改的文件列表（通常包括 components.py 和 workflow_builder.py）",
            "- `modification_plan`: 每个文件的修改说明",
            "- `components`: **新的组件列表**（必填，包含所有组件，包括保留的和新增的）",
            "- `workflow_structure`: **新的工作流拓扑结构**（必填，包含 start/edges/end）",
            "",
            "**components 格式**：",
            '[{"component_id": "start", "component_name": "开始组件", "component_type": "Start", "description": "..."}, ...]',
            "",
            "**workflow_structure 格式**：",
            '{"start": "start", "edges": [{"from": "start", "to": "component1"}, ...], "end": "end"}',
            "",
            "请根据所有需求（历史 + 当前）生成完整的新工作流结构。"
        ]
    
    def _build_generic_analysis_instructions(self) -> List[str]:
        """构建通用模式的分析指令"""
        return [
            "",
            "## 任务",
            "分析上述所有需求（历史需求 + 当前需求），确定需要修改哪些文件。",
            "",
            "请考虑：",
            "1. 哪些文件需要修改才能满足需求",
            "2. 每个文件需要如何修改（简要说明）",
            "",
            "输出格式（JSON）：",
            '{"files_to_modify": ["file1.py", "file2.py"], "modification_plan": {"file1.py": "修改说明1", "file2.py": "修改说明2"}}',
            "",
            "如果不需要修改任何文件，返回：",
            '{"files_to_modify": [], "modification_plan": {}}'
        ]
    
    def _get_analysis_system_prompt(self) -> str:
        """获取分析阶段的系统提示词"""
        return """你是一个专业的代码分析和工作流规划专家。
你的任务是分析用户需求，生成新的工作流结构。

要求：
1. 仔细分析所有需求（历史需求 + 当前需求），理解整体目标
2. **对于 Workflow 模式，必须生成新的 components 和 workflow_structure**
3. **通过修改工作流拓扑来满足需求，而不是在 component 文件中添加普通函数**
4. **如果需求是增加功能，应该添加新的组件节点并重新连接拓扑**
5. 准确识别需要修改的文件（通常包括 components.py 和 workflow_builder.py）
6. 为每个需要修改的文件提供简要的修改说明
7. 只返回JSON格式，不要添加其他文字

**重要**：components 和 workflow_structure 字段是必填的（对于 Workflow 模式），必须包含完整的新工作流结构。"""
    
    def _parse_analysis_response(self, response: str, available_files: List[str]) -> Dict[str, Any]:
        """解析分析响应 - 提取 files_to_modify, modification_plan, components, workflow_structure"""
        result = self._extract_json_from_response(response)
        
        if not result:
            # 如果完全解析失败，尝试从文本中提取文件名
            logger.warning("JSON解析失败，尝试从文本提取文件名")
            result = self._extract_files_from_text(response, available_files)
        else:
            # 验证和规范化结果
            result = self._validate_analysis_result(result, available_files)
        
        return result
    
    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """从响应中提取 JSON（支持多种格式）"""
        # 方法1: 尝试直接解析整个响应
        try:
            parsed = json.loads(response.strip())
            if isinstance(parsed, dict) and ("files_to_modify" in parsed or "components" in parsed):
                logger.info(f"✅ 直接解析 JSON 成功，包含字段: {list(parsed.keys())}")
                return parsed
        except json.JSONDecodeError:
            pass
        
        # 方法2: 提取 ```json ... ``` 代码块
        json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_block_pattern, response, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, dict) and ("files_to_modify" in parsed or "components" in parsed):
                    logger.info(f"✅ 从代码块提取 JSON 成功，包含字段: {list(parsed.keys())}")
                    return parsed
            except json.JSONDecodeError:
                pass
        
        # 方法3: 提取第一个完整的 JSON 对象（支持嵌套）
        # 使用更智能的括号匹配
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict) and ("files_to_modify" in parsed or "components" in parsed):
                    logger.info(f"✅ 从文本提取 JSON 成功，包含字段: {list(parsed.keys())}")
                    return parsed
            except json.JSONDecodeError:
                continue
        
        # 方法4: 尝试提取并修复常见的 JSON 格式问题
        # 移除可能的 markdown 格式标记
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # 移除代码块标记
            lines = cleaned.split("\n")
            if len(lines) > 1:
                cleaned = "\n".join(lines[1:-1]).strip()
        
        # 尝试找到 JSON 的开始和结束位置
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx >= 0 and end_idx > start_idx:
            try:
                json_str = cleaned[start_idx:end_idx + 1]
                parsed = json.loads(json_str)
                if isinstance(parsed, dict) and ("files_to_modify" in parsed or "components" in parsed):
                    logger.info(f"✅ 从清理后的文本提取 JSON 成功，包含字段: {list(parsed.keys())}")
                    return parsed
            except json.JSONDecodeError:
                pass
        
        logger.warning(f"⚠️ 所有 JSON 提取方法都失败，响应前500字符: {response[:500]}")
        return {}
    
    def _extract_files_from_text(self, response: str, available_files: List[str]) -> Dict[str, Any]:
        """从文本中提取文件名"""
        files_to_modify = [f for f in available_files if f in response]
        return {
            "files_to_modify": files_to_modify,
            "modification_plan": {f: "需要修改" for f in files_to_modify}
        }
    
    def _validate_analysis_result(
        self, result: Dict[str, Any], available_files: List[str]
    ) -> Dict[str, Any]:
        """验证和规范化分析结果"""
        # 验证文件列表
        files_to_modify = result.get("files_to_modify", [])
        result["files_to_modify"] = [f for f in files_to_modify if f in available_files]
        
        # 验证工作流模式的关键字段
        is_workflow = "workflow_builder.py" in available_files or "components.py" in available_files
        if is_workflow:
            if "components" not in result or not result.get("components"):
                logger.warning("⚠️ 工作流模式但缺少 components 字段，将使用现有组件")
            if "workflow_structure" not in result or not result.get("workflow_structure"):
                logger.warning("⚠️ 工作流模式但缺少 workflow_structure 字段，将使用现有结构")
        
        return result
    
    def _build_thinking_prompt_for_analysis(
        self,
        modification_request: str,
        all_requirements: List[str],
        files: Dict[str, str]
    ) -> str:
        """构建分析修改需求的思考提示词（包含完整文件信息和参考文档）"""
        requirements_text = "\n".join([f"{i}. {req}" for i, req in enumerate(all_requirements, 1)])
        
        # 加载参考文档
        modification_guide = self._load_modification_guide()
        framework_rules = self._load_framework_rules()
        
        # 构建文件内容摘要（显示关键文件的部分内容作为上下文）
        files_context = []
        for filename in sorted(files.keys()):
            content = files[filename]
            # 对于关键文件，显示前500字符作为上下文
            if filename in ["workflow_builder.py", "components.py", "config.py", "main.py"]:
                preview = content[:500] + "..." if len(content) > 500 else content
                files_context.append(f"### {filename} (前500字符预览)\n```python\n{preview}\n```")
            else:
                files_context.append(f"- {filename} ({len(content)} 字符)")
        
        files_section = "\n\n".join(files_context)
        
        prompt = f"""## 修改需求
当前需求: {modification_request}

## 所有需求（历史需求 + 当前需求）
{requirements_text}

## 当前工作流文件（完整列表）
{files_section}

## 参考文档

### 工作流修改指南
{modification_guide if modification_guide else "（未加载）"}

### 框架规范
{framework_rules if framework_rules else "（未加载）"}

## 思考任务
作为一个资深程序员，用第一人称口语化的方式思考这个修改需求。

要求：
- 200-300字左右
- 口语化，像自言自语："嗯，这个需求..."、"让我看看..."、"需要..."、"关键是要..."
- 要分析：这个需求要做什么、需要修改哪些文件、为什么要这样改、有什么注意点
- 如果是工作流模式，要考虑是否需要添加新组件、修改拓扑结构
- 参考上述修改指南和框架规范，确保修改符合规范
- 最后给出简要的分析思路

开始思考："""
        
        return prompt
    
    def _build_thinking_prompt_for_modify(
        self,
        file_path: str,
        modification_request: str,
        all_requirements: List[str],
        all_files: Optional[Dict[str, str]] = None,
        components: Optional[List[Dict[str, Any]]] = None,
        workflow_structure: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建修改文件的思考提示词（包含完整上下文信息）"""
        requirements_text = "\n".join([f"{i}. {req}" for i, req in enumerate(all_requirements, 1)])
        
        # 加载参考文档
        modification_guide = self._load_modification_guide()
        framework_rules = self._load_framework_rules()
        
        prompt_parts = [
            "## 需要修改的文件",
            file_path,
            "",
            "## 所有需求（历史需求 + 当前需求）",
            requirements_text,
            ""
        ]
        
        # 如果是工作流文件且有新的结构，添加结构信息
        is_workflow_file = file_path in ["workflow_builder.py", "components.py"]
        if is_workflow_file and components and workflow_structure:
            prompt_parts.extend([
                "## 新的工作流结构",
                f"### 组件列表（components）",
                f"共 {len(components)} 个组件",
                "",
                f"### 工作流拓扑（workflow_structure）",
                f"包含 {len(workflow_structure.get('edges', []))} 条连接",
                ""
            ])
        
        # 添加其他文件作为上下文（显示文件名和大小）
        if all_files:
            prompt_parts.extend([
                "## 其他文件（作为上下文）",
            ])
            for filename in sorted(all_files.keys()):
                if filename != file_path:
                    content = all_files[filename]
                    prompt_parts.append(f"- {filename} ({len(content)} 字符)")
            prompt_parts.append("")
        
        # 添加参考文档
        prompt_parts.extend([
            "## 参考文档",
            "",
            "### 工作流修改指南",
            modification_guide[:1000] + "..." if modification_guide and len(modification_guide) > 1000 else (modification_guide or "（未加载）"),
            "",
            "### 框架规范",
            framework_rules[:1000] + "..." if framework_rules and len(framework_rules) > 1000 else (framework_rules or "（未加载）"),
            ""
        ])
        
        prompt_parts.extend([
            "## 思考任务",
            "作为一个资深程序员，用第一人称口语化的方式思考这个文件需要怎么修改。",
            "",
            "要求：",
            "- 200-300字左右",
            '- 口语化，像自言自语："嗯，这个文件..."、"让我看看..."、"需要..."、"关键是要..."',
            "- 要分析：这个文件的作用是什么、需要改哪些地方、为什么要这样改、有什么注意点",
            "- 如果是工作流文件，要参考新的工作流结构和修改指南",
            "- 确保修改符合框架规范",
            "- 最后给出简要的修改思路",
            "",
            "开始思考："
        ])
        
        return "\n".join(prompt_parts)
    
    def _build_modify_prompt(
        self,
        file_path: str,
        file_content: str,
        modification_request: str,
        all_requirements: List[str],
        all_files: Dict[str, str],
        thinking_context: Optional[str] = None,
        components: Optional[List[Dict[str, Any]]] = None,
        workflow_structure: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建修改提示词 - 对于 workflow 模式，使用新的工作流结构"""
        prompt_parts = []
        
        # 如果有思考过程，添加到前面
        if thinking_context:
            prompt_parts.extend([
                "## Agent 思考过程",
                thinking_context,
                "",
                "---",
                ""
            ])
        
        prompt_parts.extend([
            "## 修改需求",
            f"当前需求: {modification_request}",
            "",
            "## 所有需求（历史需求 + 当前需求）",
        ])
        
        for i, req in enumerate(all_requirements, 1):
            prompt_parts.append(f"{i}. {req}")
        
        # 对于 workflow 模式的关键文件，添加新的工作流结构
        is_workflow_file = file_path in ["workflow_builder.py", "components.py"]
        if is_workflow_file and components and workflow_structure:
            prompt_parts.extend(self._build_workflow_structure_section(
                components, workflow_structure, file_path
            ))
        
        prompt_parts.extend([
            "",
            f"## 需要修改的文件: {file_path}",
            "```python",
            file_content,  # 显示完整内容
            "```",
            ""
        ])
        
        # 添加其他文件作为上下文（显示所有文件的完整内容）
        if len(all_files) > 1:
            prompt_parts.append("## 其他文件（作为上下文参考，完整内容）")
            other_files = {k: v for k, v in all_files.items() if k != file_path}
            for filename, content in sorted(other_files.items()):
                prompt_parts.extend([
                    f"### {filename}",
                    "```python",
                    content,  # 显示完整内容，不截断
                    "```",
                    ""
                ])
        
        # 添加参考文档
        modification_guide = self._load_modification_guide()
        framework_rules = self._load_framework_rules()
        
        if is_workflow_file:
            prompt_parts.extend([
                "",
                "## 参考文档",
                "",
                "### 工作流修改指南",
                modification_guide if modification_guide else "（未加载）",
                "",
                "### 框架规范",
                framework_rules if framework_rules else "（未加载）",
                ""
            ])
        
        # 根据文件类型添加不同的要求
        if is_workflow_file and components and workflow_structure:
            prompt_parts.extend([
                "## 要求",
                f"根据上述所有需求和新的工作流结构，修改 {file_path} 文件。",
                "",
                f"**对于 {file_path} 的特殊要求**：",
                f"- 如果修改 `workflow_builder.py`：必须根据新的 `workflow_structure` 重新构建 `build_workflow()` 函数中的拓扑连接（edges）",
                f"- 如果修改 `components.py`：必须根据新的 `components` 列表添加或修改组件创建函数（如 `create_xxx_component`）",
                f"- **严禁**在 `components.py` 中添加普通辅助函数（如 `format_recommendations_as_letter`）",
                f"- **必须**通过添加新组件并更新工作流拓扑来满足需求",
                "",
                "只输出修改后的完整代码，使用 ```python 代码块包裹。",
                "保持代码风格一致，符合 openJiuwen 框架规范。",
                "如果不需要修改，输出原代码。"
            ])
        else:
            prompt_parts.extend([
                "## 要求",
                f"根据上述所有需求，修改 {file_path} 文件。",
                "只输出修改后的完整代码，使用 ```python 代码块包裹。",
                "保持代码风格一致，符合 openJiuwen 框架规范。",
                "如果不需要修改，输出原代码。"
            ])
        
        return "\n".join(prompt_parts)
    
    def _get_modify_system_prompt(self) -> str:
        """获取修改阶段的系统提示词"""
        return """你是一个专业的代码修改专家。
你的任务是根据用户需求修改代码文件。

要求：
1. 仔细理解所有需求（历史需求 + 当前需求），确保修改满足整体目标
2. **对于 workflow 模式的关键文件（workflow_builder.py 和 components.py）**：
   - 如果提供了新的 `components` 和 `workflow_structure`，必须严格按照这些结构来修改
   - **严禁**在 `components.py` 中添加普通辅助函数（如 `format_recommendations_as_letter`）
   - **必须**通过添加新组件并更新工作流拓扑来满足需求
   - 修改 `workflow_builder.py` 时，必须根据新的 `workflow_structure` 重新构建拓扑连接
3. 修改后的代码必须符合 openJiuwen 框架规范（参考 framework-rules.md）
4. 保持代码风格一致
5. 只输出修改后的完整代码，不要添加解释文字
6. 如果不需要修改，输出原代码

**常见错误避免**：
- 不要创建多个 End 组件（只能有一个）
- Start 组件的输入变量名必须为 `query`
- IntentDetectionComponent 和 BranchComponent 必须使用 `add_branch`，不能使用 `add_connection`
- 所有组件的 `inputs_schema` 必须正确引用上游组件的输出变量"""
    
    def _parse_modify_response(self, response: str, original_content: str) -> str:
        """解析修改响应，提取修改后的代码"""
        import re
        
        # 尝试提取代码块
        pattern = r'```python\s*\n(.*?)```'
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # 如果没有代码块，检查是否包含原代码的明显标识
        # 如果响应太短或看起来不像代码，返回原内容
        if len(response.strip()) < len(original_content) * 0.5:
            logger.warning("响应看起来不完整，返回原内容")
            return original_content
        
        # 否则返回响应（去除可能的markdown格式）
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if len(lines) > 1:
                return "\n".join(lines[1:-1]).strip()
        
        return cleaned
    
    def _build_workflow_structure_section(
        self,
        components: List[Dict[str, Any]],
        workflow_structure: Dict[str, Any],
        file_path: str
    ) -> List[str]:
        """构建工作流结构说明部分"""
        return [
            "",
            "## ⚠️ 重要：新的工作流结构",
            "**必须根据以下新的工作流结构来修改文件，而不是添加普通函数！**",
            "",
            "### 新的组件列表（components）",
            "```json",
            json.dumps(components, ensure_ascii=False, indent=2),
            "```",
            "",
            "### 新的工作流拓扑结构（workflow_structure）",
            "```json",
            json.dumps(workflow_structure, ensure_ascii=False, indent=2),
            "```",
            "",
            "**修改原则**：",
            f"- 如果修改 `workflow_builder.py`：必须根据新的 `workflow_structure` 重新构建工作流拓扑（edges）",
            f"- 如果修改 `components.py`：必须根据新的 `components` 列表添加或修改组件创建函数",
            f"- **不要**在 `components.py` 中添加普通函数（如 `format_recommendations_as_letter`），而应该添加新的组件",
            f"- **必须**通过修改工作流拓扑来满足需求，而不是在代码中添加辅助函数",
            ""
        ]
    
    def _build_modification_request_from_errors(self, error_info: Dict[str, Any]) -> str:
        """
        从错误信息生成修改需求（用于场景2：错误修复）
        
        Args:
            error_info: 错误信息 {test_output, errors, failed_tests, test_command}
        
        Returns:
            修改需求字符串
        """
        test_output = error_info.get("test_output", "")
        errors = error_info.get("errors", "")
        failed_tests = error_info.get("failed_tests", [])
        test_command = error_info.get("test_command", "")
        
        request_parts = [
            "修复代码错误，确保工作流能够正常运行。",
            "",
            "## 错误信息",
        ]
        
        if test_output:
            request_parts.append(f"测试输出:\n{test_output}")
        
        if errors:
            request_parts.append(f"\n错误信息:\n{errors}")
        
        if failed_tests:
            if isinstance(failed_tests, list):
                request_parts.append(f"\n失败的测试用例: {', '.join(failed_tests)}")
            else:
                request_parts.append(f"\n失败的测试用例: {failed_tests}")
        
        if test_command:
            request_parts.append(f"\n执行的测试命令: {test_command}")
        
        request_parts.extend([
            "",
            "## 要求",
            "请分析错误原因，定位问题，并修复代码中的问题。",
            "确保修复后的代码能够正常运行，通过所有测试。",
            "如果涉及工作流结构问题，需要修改工作流拓扑结构。"
        ])
        
        return "\n".join(request_parts)