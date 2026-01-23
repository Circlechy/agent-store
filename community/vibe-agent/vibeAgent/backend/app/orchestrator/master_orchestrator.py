"""
主协调器（MasterOrchestrator）

只协调不执行，负责意图识别、任务规划、任务委托、结果验证
"""
from typing import Dict, Any, Optional, AsyncIterator, List
from pathlib import Path
from datetime import datetime
import re
import asyncio
from loguru import logger

from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.agent.config.base import AgentConfig

from app.agents.base import VibeBaseAgent
from app.context.context_manager import ContextManager
from app.session.session_manager import SessionManager
from app.skills.skill_manager import SkillManager
from app.wisdom.wisdom_manager import WisdomManager
from app.orchestrator.delegation_tool import DelegationTool
from app.orchestrator.result_verifier import ResultVerifier
from app.models.agent_result import AgentResult
from app.models.task import (
    TaskPlan, TodoItem, ModePlan,
    AgentMode, IntentType, CodebaseState
)
from app.models.events import SSEEvent, EventType
from app.utils import normalize_agent_mode


def _get_file_display_name(file_name: str, agent_mode: str) -> str:
    """
    获取文件的显示名称（描述性名称）
    
    Args:
        file_name: 文件名（如 config.py）
        agent_mode: Agent 模式（workflow/react/multi_agent）
    
    Returns:
        描述性名称（如 "生成配置文件"）
    """
    # 通用映射
    common_map = {
        "config.py": "生成配置文件",
        "main.py": "生成主执行文件",
    }
    
    # 模式特定映射
    mode_specific_map = {
        "workflow": {
            "components.py": "生成组件文件",
            "workflow_builder.py": "生成工作流连接文件",
        },
        "react": {
            "local_agent.py": "生成 Agent 逻辑文件",
        },
        "multi_agent": {
            "leader_agent.py": "生成 Leader Agent 文件",
            "worker_agents.py": "生成 Worker Agents 文件",
        }
    }
    
    # 先检查通用映射
    if file_name in common_map:
        return common_map[file_name]
    
    # 再检查模式特定映射
    if agent_mode in mode_specific_map:
        if file_name in mode_specific_map[agent_mode]:
            return mode_specific_map[agent_mode][file_name]
    
    # 如果没有匹配，使用文件名（去除 .py）
    base_name = file_name.replace(".py", "")
    return f"生成 {base_name} 文件"


def _get_step_type(file_name: str) -> str:
    """
    根据文件名获取步骤类型
    
    Args:
        file_name: 文件名
    
    Returns:
        步骤类型：config/component/execution
    """
    if file_name == "config.py":
        return "config"
    if "component" in file_name.lower():
        return "component"
    return "execution"


def _create_mode_plan(mode_plan_data: Dict[str, Any], agent_mode: AgentMode) -> ModePlan:
    """
    根据 Agent 模式创建对应的 ModePlan 对象
    
    Args:
        mode_plan_data: 模式计划数据
        agent_mode: Agent 模式
    
    Returns:
        ModePlan 实例
    """
    from app.models.task import WorkflowPlan, ReActPlan, MultiAgentPlan
    
    plan_class_map = {
        AgentMode.WORKFLOW: WorkflowPlan,
        AgentMode.REACT: ReActPlan,
        AgentMode.MULTI_AGENT: MultiAgentPlan,
    }
    
    plan_class = plan_class_map.get(agent_mode, ModePlan)
    return plan_class(**mode_plan_data)


def _build_file_to_step_id_map(required_files: List[str]) -> Dict[str, str]:
    """
    构建文件名到 step_id 的映射
    
    Args:
        required_files: 必需文件列表
    
    Returns:
        文件名到 step_id 的映射字典
    """
    return {file_name: f"generate_{idx}" for idx, file_name in enumerate(required_files)}


def _build_test_result_data(result_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    构建标准化的测试结果数据结构
    
    Args:
        result_data: TesterAgent 返回的原始数据
    
    Returns:
        标准化的测试结果数据
    """
    if not result_data:
        return {}
    
    tests_passed = result_data.get("tests_passed", False)
    test_output = result_data.get("test_output", "")
    errors = result_data.get("errors")
    test_command = result_data.get("command", "")
    smoke_tests = result_data.get("smoke_tests", [])
    
    return {
        "success": tests_passed,
        "tests_passed": tests_passed,
        "test_output": test_output,
        "output": test_output,
        "error": errors,
        "errors": errors,
        "execution_time": result_data.get("execution_time", 0.0),
        "command": test_command,
        "test_cases": smoke_tests if smoke_tests else ([test_command] if test_command else []),
    }


def _normalize_workflow_dir(workflow_dir: str) -> str:
    """
    将工作流目录路径标准化为绝对路径
    
    Args:
        workflow_dir: 工作流目录（相对或绝对路径）
    
    Returns:
        绝对路径
    """
    if not Path(workflow_dir).is_absolute():
        project_root = Path(__file__).parent.parent.parent.parent
        return str(project_root / workflow_dir)
    return workflow_dir


def _extract_workflow_name(workflow_dir: str) -> str:
    """
    从工作流目录路径提取工作流名称
    
    Args:
        workflow_dir: 工作流目录路径
    
    Returns:
        工作流名称
    """
    workflow_path = Path(workflow_dir)
    return workflow_path.name if workflow_path.name else str(workflow_path)


def _detect_agent_mode_from_workflow_dir(workflow_dir: str) -> Optional[AgentMode]:
    """
    从工作流目录的文件中推断 Agent 模式
    
    Args:
        workflow_dir: 工作流目录路径
    
    Returns:
        AgentMode 或 None（如果无法推断）
    """
    workflow_path = Path(workflow_dir)
    if not workflow_path.exists():
        return None
    
    # 检查文件列表
    py_files = {f.name for f in workflow_path.glob("*.py")}
    
    # Workflow 模式：包含 workflow_builder.py 或 components.py
    if "workflow_builder.py" in py_files or "components.py" in py_files:
        return AgentMode.WORKFLOW
    
    # ReAct 模式：包含 local_agent.py
    if "local_agent.py" in py_files:
        return AgentMode.REACT
    
    # Multi-Agent 模式：包含 leader_agent.py 或 worker_agents.py
    if "leader_agent.py" in py_files or "worker_agents.py" in py_files:
        return AgentMode.MULTI_AGENT
    
    # 默认返回 None（无法推断）
    return None


def _generate_workflow_dir_name(user_input: str, max_length: int = 50) -> str:
    """
    根据日期和用户输入生成工作流目录名
    
    Args:
        user_input: 用户输入
        max_length: 目录名最大长度（不包括日期部分）
    
    Returns:
        目录名，格式：YYYYMMDD_HHMMSS_用户输入（截断）
    """
    # 生成日期时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 系统化清理用户输入，确保生成安全的目录名
    # 1. 先去除首尾空白字符（包括换行符、制表符、空格等）
    cleaned_input = user_input.strip()
    
    # 2. 移除所有控制字符（包括换行符 \n、制表符 \t、回车符 \r 等）
    # \x00-\x1f: ASCII 控制字符（0-31），包括换行符 \n (0x0a)、制表符 \t (0x09)、回车符 \r (0x0d)
    # \x7f-\x9f: DEL 和扩展控制字符（127-159）
    cleaned_input = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned_input)
    
    # 3. 移除 Windows 非法字符：< > : " | ? * \ /
    cleaned_input = re.sub(r'[<>:"|?*\\/]', '', cleaned_input)
    
    # 4. 保留：字母、数字、中文、下划线、连字符、空格
    cleaned_input = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', cleaned_input)
    
    # 5. 将所有空白字符（空格、制表符等）替换为下划线
    cleaned_input = re.sub(r'\s+', '_', cleaned_input)
    
    # 6. 将多个连续的下划线合并为一个
    cleaned_input = re.sub(r'_+', '_', cleaned_input)
    
    # 7. 去除首尾的下划线
    cleaned_input = cleaned_input.strip('_')
    
    # 8. 截断到指定长度
    if len(cleaned_input) > max_length:
        cleaned_input = cleaned_input[:max_length]
        # 如果截断后末尾是下划线，移除它
        cleaned_input = cleaned_input.rstrip('_')
    
    # 如果用户输入为空或清理后为空，使用默认名称
    if not cleaned_input:
        cleaned_input = "untitled"
    
    # 组合：日期_用户输入
    dir_name = f"{timestamp}_{cleaned_input}"
    
    return dir_name


class MasterOrchestrator(VibeBaseAgent):
    """
    主协调器 - 继承 openJiuwen.BaseAgent
    
    关键约束：
    - ❌ 禁止直接执行任务（不能写文件、修改文件、执行代码）
    - ✅ 只能使用 delegate_task 工具委托任务
    - ✅ 必须验证子 Agent 的结果
    """
    
    # 类常量
    SKILL_NAME_MAP = {
        "workflow": "workflow-generation-skill",
        "react": "react-agent-skill",
        "multi_agent": "multi-agent-skill"
    }
    
    MODE_HINTS = {
        "workflow": "工作流模式需要定义组件（Start/End/LLMNode/ToolNode等）、连接关系、数据流向",
        "react": "ReAct模式需要定义工具列表、Agent配置、思考-行动-观察循环逻辑",
        "multi_agent": "多Agent模式需要定义Leader/Worker角色、任务分配策略、协作机制"
    }
    
    THINKING_SYSTEM_PROMPT = """你是一位资深程序员，用口语化的方式表达思考。像在心里嘀咕一样，简短有力，不要书面化。"""
    
    def _get_modification_metadata(self, task_plan: TaskPlan) -> Dict[str, Any]:
        """
        获取修改元数据
        
        Args:
            task_plan: 任务计划
        
        Returns:
            修改元数据字典
        """
        return getattr(task_plan, '_modification_metadata', {})
    
    def _set_modification_metadata(
        self,
        task_plan: TaskPlan,
        files_to_modify: List[str],
        modification_plan: Dict[str, str],
        all_files: Dict[str, str],
        all_requirements: List[str],
        components: Optional[List[Dict[str, Any]]] = None,
        workflow_structure: Optional[Dict[str, Any]] = None
    ):
        """
        设置修改元数据
        
        Args:
            task_plan: 任务计划
            files_to_modify: 需要修改的文件列表
            modification_plan: 修改计划
            all_files: 所有文件内容
            all_requirements: 所有需求
            components: 新的组件列表（可选，用于 workflow 模式）
            workflow_structure: 新的工作流结构（可选，用于 workflow 模式）
        """
        if not hasattr(task_plan, '_modification_metadata'):
            task_plan._modification_metadata = {}
        task_plan._modification_metadata = {
            "files_to_modify": files_to_modify,
            "modification_plan": modification_plan,
            "all_files": all_files,
            "all_requirements": all_requirements,
            "components": components or [],
            "workflow_structure": workflow_structure or {}
        }
    
    def _get_file_to_modify(self, todo: TodoItem, task_plan: TaskPlan) -> Optional[str]:
        """
        确定要修改的文件
        
        Args:
            todo: 当前任务项
            task_plan: 任务计划
        
        Returns:
            要修改的文件名，如果无法确定则返回 None
        """
        # 优先从 todo 的 expected_files 获取
        if todo.expected_files:
            return todo.expected_files[0]
        
        # 从 metadata 中获取
        metadata = self._get_modification_metadata(task_plan)
        files_to_modify = metadata.get("files_to_modify", [])
        if files_to_modify:
            # 找到第一个还未处理的文件
            completed_files = [
                t.expected_files[0] for t in task_plan.todos[:task_plan.current_index]
                if t.task_type == "modify_file" and t.expected_files
            ]
            return next(
                (f for f in files_to_modify if f not in completed_files),
                files_to_modify[0] if files_to_modify else None
            )
        
        return None
    
    def _load_all_python_files(self, workflow_dir: str, generated_files: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        读取工作流目录中的所有 Python 文件
        
        Args:
            workflow_dir: 工作流目录
            generated_files: 已生成的文件字典（可选，用于合并）
        
        Returns:
            文件字典 {文件名: 内容}
        """
        all_files = {}
        workflow_path = Path(workflow_dir)
        
        for py_file in workflow_path.glob("*.py"):
            try:
                all_files[py_file.name] = py_file.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"读取文件失败 {py_file.name}: {e}")
        
        # 如果提供了 generated_files，合并进去
        if generated_files:
            all_files.update(generated_files)
        
        return all_files
    
    def _load_file_content(
        self,
        file_name: str,
        workflow_dir: str,
        all_files: Dict[str, str]
    ) -> Optional[str]:
        """
        加载文件内容
        
        Args:
            file_name: 文件名
            workflow_dir: 工作流目录
            all_files: 文件缓存字典
        
        Returns:
            文件内容，如果文件不存在则返回 None
        """
        # 先从缓存获取
        if file_name in all_files:
            return all_files[file_name]
        
        # 从文件系统读取
        file_path = Path(workflow_dir) / file_name
        if file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8")
                all_files[file_name] = content
                return content
            except Exception as e:
                logger.error(f"读取文件失败 {file_name}: {e}")
                return None
        
        return None
    
    def _save_modified_file(
        self,
        file_name: str,
        content: str,
        workflow_dir: str,
        generated_files: Dict[str, str]
    ) -> bool:
        """
        保存修改后的文件
        
        Args:
            file_name: 文件名
            content: 文件内容
            workflow_dir: 工作流目录
            generated_files: 生成的文件字典（用于更新）
        
        Returns:
            是否保存成功
        """
        try:
            file_path = Path(workflow_dir) / file_name
            file_path.write_text(content, encoding="utf-8")
            generated_files[file_name] = content
            logger.info(f"✅ 文件已保存: {file_name}")
            return True
        except Exception as e:
            logger.error(f"保存文件失败 {file_name}: {e}")
            return False
    
    def _add_modify_file_tasks(self, task_plan: TaskPlan, files_to_modify: List[str]):
        """
        动态添加 modify_file 任务到任务计划
        
        Args:
            task_plan: 任务计划
            files_to_modify: 需要修改的文件列表
        """
        analyze_idx = task_plan.current_index
        for file_name in files_to_modify:
            modify_todo = TodoItem(
                task_type="modify_file",
                description=f"修改 {file_name}",
                mode=None,
                category=None,
                skills=[],
                expected_files=[file_name],
                expected_outcome=f"完成 {file_name} 的修改",
                max_retries=1
            )
            # 插入到 analyze_modification 之后
            task_plan.todos.insert(analyze_idx + 1, modify_todo)
    
    def _add_fix_errors_task(
        self,
        task_plan: TaskPlan,
        error_info: Dict[str, Any],
        workflow_dir: str,
        files: Dict[str, str],
        fix_test_cycle_count: int = 0,
        modify_test_cycle_count: Optional[int] = None
    ):
        """
        动态添加修复错误任务到任务计划
        
        Args:
            task_plan: 任务计划
            error_info: 错误信息 {test_output, errors, failed_tests, test_command}
            workflow_dir: 工作流目录
            files: 当前所有文件内容
            fix_test_cycle_count: 修复-测试循环次数（用于场景2：执行失败修复）
            modify_test_cycle_count: 修改-测试循环次数（用于场景1：用户增量修改，可选）
        """
        # 检查是否已经存在修复任务（避免重复添加）
        existing_fix_tasks = [
            t for t in task_plan.todos[task_plan.current_index + 1:]
            if t.task_type == "fix_errors"
        ]
        if existing_fix_tasks:
            logger.info("⚠️ 已存在修复任务，跳过添加")
            return
        
        fix_todo = TodoItem(
            task_type="fix_errors",
            description="修复代码错误",
            mode=None,
            category=None,
            skills=[],
            expected_files=[],
            expected_outcome="修复所有代码错误，确保工作流能够正常运行",
            max_retries=2  # 允许重试2次
        )
        
        # 保存错误信息到 todo 的 metadata
        fix_todo.metadata['error_info'] = error_info
        fix_todo.metadata['workflow_dir'] = workflow_dir
        fix_todo.metadata['files'] = files
        fix_todo.metadata['fix_test_cycle_count'] = fix_test_cycle_count
        
        # 如果是场景1（用户修改），保存修改-测试循环次数
        if modify_test_cycle_count is not None:
            fix_todo.metadata['modify_test_cycle_count'] = modify_test_cycle_count
        
        # 插入到当前任务之后
        current_idx = task_plan.current_index
        task_plan.todos.insert(current_idx + 1, fix_todo)
        logger.info(f"✅ 已添加修复任务到任务计划（位置: {current_idx + 1}，修复-测试循环次数: {fix_test_cycle_count}）")
    
    def _add_test_task_after_fix(
        self,
        task_plan: TaskPlan,
        agent_mode: Optional[AgentMode],
        fix_test_cycle_count: int
    ):
        """
        在修复任务后动态添加测试任务（场景2：执行失败修复）
        
        Args:
            task_plan: 任务计划
            agent_mode: Agent 模式
            fix_test_cycle_count: 修复-测试循环次数
        """
        self._add_test_task_after_fix_or_modify(
            task_plan=task_plan,
            agent_mode=agent_mode,
            is_modify_scenario=False,
            modify_test_cycle_count=None,
            fix_test_cycle_count=fix_test_cycle_count
        )
    
    def _extract_cycle_counts_from_todo(self, todo: TodoItem) -> tuple[bool, Optional[int], int]:
        """
        从 todo.metadata 中提取循环次数和判断场景
        
        Args:
            todo: TODO 项
        
        Returns:
            (is_modify_scenario, modify_test_cycle_count, fix_test_cycle_count)
        """
        is_modify_scenario = False
        modify_test_cycle_count = None
        fix_test_cycle_count = 0
        
        if todo.metadata:
            if 'modify_test_cycle_count' in todo.metadata:
                is_modify_scenario = True
                modify_test_cycle_count = todo.metadata.get('modify_test_cycle_count', 0)
            elif 'fix_test_cycle_count' in todo.metadata:
                fix_test_cycle_count = todo.metadata.get('fix_test_cycle_count', 0)
        
        return is_modify_scenario, modify_test_cycle_count, fix_test_cycle_count
    
    def _should_add_test_after_fix(
        self,
        is_modify_scenario: bool,
        modify_test_cycle_count: Optional[int],
        fix_test_cycle_count: int,
        max_modify_cycles: int = 3,
        max_fix_cycles: int = 3
    ) -> tuple[bool, Optional[int], int]:
        """
        判断修复后是否应该添加测试任务，并返回更新后的循环次数
        
        Args:
            is_modify_scenario: 是否是场景1（用户修改）
            modify_test_cycle_count: 修改-测试循环次数
            fix_test_cycle_count: 修复-测试循环次数
            max_modify_cycles: 最大修改-测试循环次数
            max_fix_cycles: 最大修复-测试循环次数
        
        Returns:
            (should_add_test, updated_modify_count, updated_fix_count)
        """
        if is_modify_scenario:
            if modify_test_cycle_count is not None and modify_test_cycle_count < max_modify_cycles:
                return True, modify_test_cycle_count + 1, fix_test_cycle_count
        else:
            if fix_test_cycle_count < max_fix_cycles:
                return True, modify_test_cycle_count, fix_test_cycle_count + 1
        
        return False, modify_test_cycle_count, fix_test_cycle_count
    
    def _add_test_task_after_fix_or_modify(
        self,
        task_plan: TaskPlan,
        agent_mode: Optional[AgentMode],
        is_modify_scenario: bool,
        modify_test_cycle_count: Optional[int],
        fix_test_cycle_count: int,
        max_modify_cycles: int = 3,
        max_fix_cycles: int = 3
    ):
        """
        在修复或修改任务后动态添加测试任务
        
        Args:
            task_plan: 任务计划
            agent_mode: Agent 模式
            is_modify_scenario: 是否是场景1（用户修改）
            modify_test_cycle_count: 修改-测试循环次数
            fix_test_cycle_count: 修复-测试循环次数
            max_modify_cycles: 最大修改-测试循环次数
            max_fix_cycles: 最大修复-测试循环次数
        """
        should_add, updated_modify_count, updated_fix_count = self._should_add_test_after_fix(
            is_modify_scenario, modify_test_cycle_count, fix_test_cycle_count,
            max_modify_cycles, max_fix_cycles
        )
        
        if not should_add:
            max_cycles = max_modify_cycles if is_modify_scenario else max_fix_cycles
            logger.warning(f"⚠️ 已达到最大循环次数 ({max_cycles})，不再自动添加测试任务")
            return
        
        if agent_mode is None:
            logger.warning(f"⚠️ 无法推断 agent_mode，跳过自动测试")
            return
        
        # 检查是否已经存在测试任务（避免重复添加）
        existing_test_tasks = [
            t for t in task_plan.todos[task_plan.current_index + 1:]
            if t.task_type == "test"
        ]
        if existing_test_tasks:
            logger.info("⚠️ 已存在测试任务，跳过添加")
            return
        
        test_todo = TodoItem(
            task_type="test",
            description="测试修复后的代码" if not is_modify_scenario else "测试修改后的代码",
            mode=agent_mode,
            category=None,
            skills=[],
            expected_files=[],
            expected_outcome="所有测试通过",
            max_retries=0
        )
        
        # 保存循环次数到 metadata
        if is_modify_scenario:
            test_todo.metadata['modify_test_cycle_count'] = updated_modify_count
            cycle_info = f"修改-测试循环: {updated_modify_count}/{max_modify_cycles}"
        else:
            test_todo.metadata['fix_test_cycle_count'] = updated_fix_count
            cycle_info = f"修复-测试循环: {updated_fix_count}/{max_fix_cycles}"
        
        # 插入到当前任务之后
        current_idx = task_plan.current_index
        task_plan.todos.insert(current_idx + 1, test_todo)
        logger.info(f"✅ 已添加测试任务到任务计划（位置: {current_idx + 1}，{cycle_info}）")
    
    def _add_test_task_after_modify(
        self,
        task_plan: TaskPlan,
        agent_mode: Optional[AgentMode],
        modify_test_cycle_count: int
    ):
        """
        在修改任务后动态添加测试任务（场景1：用户增量修改）
        
        Args:
            task_plan: 任务计划
            agent_mode: Agent 模式
            modify_test_cycle_count: 修改-测试循环次数
        """
        self._add_test_task_after_fix_or_modify(
            task_plan=task_plan,
            agent_mode=agent_mode,
            is_modify_scenario=True,
            modify_test_cycle_count=modify_test_cycle_count,
            fix_test_cycle_count=0
        )
    
    async def _forward_event_queue(
        self,
        event_queue: asyncio.Queue,
        task: asyncio.Task
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        转发事件队列中的事件
        
        Args:
            event_queue: 事件队列
            task: 关联的任务（用于判断是否完成）
        
        Yields:
            事件字典
        """
        while not task.done() or not event_queue.empty():
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                if task.done():
                    # 任务完成，获取剩余事件
                    while not event_queue.empty():
                        try:
                            event = event_queue.get_nowait()
                            yield event
                        except asyncio.QueueEmpty:
                            break
                    break
                continue
    
    async def _generate_and_stream_thinking(
        self,
        thinking_prompt: str,
        step_id: str,
        step_name: str,
        runtime: Runtime
    ) -> tuple[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        """
        生成并流式输出思考过程
        
        Args:
            thinking_prompt: 思考提示词
            step_id: 步骤ID
            step_name: 步骤名称
            runtime: Runtime 实例
        
        Returns:
            (思考内容引用字典, 事件迭代器)
            注意：思考内容会在任务完成后写入引用字典的 "value" 字段
        """
        thinking_event_queue = asyncio.Queue()
        thinking_context_ref = {"value": None}  # 使用字典引用，以便在异步函数中修改
        
        async def generate_thinking():
            try:
                context = await self._generate_thinking_stream(
                    thinking_prompt=thinking_prompt,
                    system_prompt=self.THINKING_SYSTEM_PROMPT,
                    event_queue=thinking_event_queue,
                    step_id=step_id,
                    step_name=step_name,
                    runtime=runtime
                )
                thinking_context_ref["value"] = context
                return context
            except Exception as e:
                logger.warning(f"思考过程生成失败: {e}")
                thinking_context_ref["value"] = None
                return None
        
        thinking_task = asyncio.create_task(generate_thinking())
        
        # 返回事件迭代器（不等待任务完成，让调用者边消费事件边等待）
        async def event_generator():
            # 在转发事件的同时，等待任务完成
            async for event in self._forward_event_queue(thinking_event_queue, thinking_task):
                yield event
            
            # 确保任务完成（如果还没完成）
            if not thinking_task.done():
                await thinking_task
        
        # 不等待任务完成，直接返回迭代器和引用字典
        # 调用者需要等待事件迭代器完成后，再通过引用字典获取思考内容
        return thinking_context_ref, event_generator()
    
    def __init__(
        self,
        agent_config: AgentConfig,
        context_manager: ContextManager,
        session_manager: SessionManager,
        skill_manager: Optional[SkillManager] = None,
        wisdom_manager: Optional[WisdomManager] = None
    ):
        """
        初始化主协调器
        
        Args:
            agent_config: Agent 配置（必须包含 model）
            context_manager: 上下文管理器
            session_manager: 会话管理器
            skill_manager: 技能管理器
            wisdom_manager: 智慧管理器
        """
        super().__init__(agent_config, context_manager)
        
        self.session_manager = session_manager
        self.skill_manager = skill_manager or SkillManager()
        self.wisdom_manager = wisdom_manager or WisdomManager()
        
        # 创建委托工具并注册
        self.delegation_tool = DelegationTool(
            context_manager=context_manager,
            session_manager=session_manager,
            skill_manager=self.skill_manager
        )
        self.add_tools([self.delegation_tool])
        
        # 禁止的工具列表
        self._blocked_tools = [
            "write_file",
            "modify_file",
            "execute_code",
            "run_test"
        ]
        
        logger.info("初始化 MasterOrchestrator")
    
    async def invoke(self, inputs: Dict, runtime: Runtime = None) -> Dict:
        """
        实现 openJiuwen 的 invoke 接口
        
        流程：
        1. Intent Gate - 识别请求类型
        2. Codebase Assessment - 评估代码库
        3. Task Planning - 规划任务（L0 TaskPlan）
        4. Task Execution - 执行任务（委托）
        5. Result Verification - 验证结果
        6. Wisdom Accumulation - 积累智慧
        
        Args:
            inputs: 输入数据 {user_input, agent_mode, workflow_name}
            runtime: Runtime 实例
        
        Returns:
            执行结果
        """
        MAX_GLOBAL_ITERATIONS = 20  # 全局最大迭代次数，防止无限循环
        iteration_count = 0
        
        try:
            user_input = inputs.get("user_input", "")
            agent_mode_str = inputs.get("agent_mode", "workflow")
            workflow_name = inputs.get("workflow_name", "default")
            
            # 规范化 agent_mode（向后兼容：将 "agent" 映射到 "react"）
            agent_mode_str = normalize_agent_mode(agent_mode_str)
            agent_mode = AgentMode(agent_mode_str)
            
            # 如果未提供 workflow_dir，根据日期和用户输入生成目录名
            if "workflow_dir" not in inputs or not inputs.get("workflow_dir"):
                dir_name = _generate_workflow_dir_name(user_input)
                workflow_dir = f"experiments/{dir_name}"
                # 更新 workflow_name 为生成的目录名（用于智慧管理）
                workflow_name = dir_name
            else:
                workflow_dir = inputs.get("workflow_dir")
            
            # 将相对路径转换为绝对路径（基于项目根目录）
            if not Path(workflow_dir).is_absolute():
                # 获取项目根目录（backend_v3 的父目录的父目录）
                project_root = Path(__file__).parent.parent.parent.parent
                workflow_dir = str(project_root / workflow_dir)
            
            # 确保目录存在
            Path(workflow_dir).mkdir(parents=True, exist_ok=True)
            
            logger.info(f"🚀 开始执行任务: mode={agent_mode_str}, workflow={workflow_name}")
            logger.info(f"📁 工作流目录: {workflow_dir}")
            
            # 阶段 0: 意图识别和代码库评估
            intent_type = await self._intent_gate(user_input)
            codebase_state = await self._assess_codebase(workflow_dir)
            logger.info(f"📊 意图类型: {intent_type.value}, 代码库状态: {codebase_state.value}")
            
            # 读取智慧
            wisdom = self.wisdom_manager.read_wisdom(workflow_name)
            
            # 阶段 1: 任务规划（L0 TaskPlan）
            task_plan = await self._plan_tasks(user_input, codebase_state, agent_mode)
            total_todos = len(task_plan.todos)
            logger.info(f"📋 任务规划完成: 共 {total_todos} 个步骤")
            
            # 阶段 2-4: 执行任务并验证
            results = []
            mode_plan = None
            
            while not task_plan.is_complete():
                iteration_count += 1
                if iteration_count > MAX_GLOBAL_ITERATIONS:
                    logger.error(f"❌ 达到最大迭代次数 ({MAX_GLOBAL_ITERATIONS})，强制终止")
                    break
                
                todo = task_plan.get_current_todo()
                if not todo:
                    logger.warning("⚠️ 获取当前 TODO 失败，终止循环")
                    break
                
                current_idx = task_plan.current_index + 1
                logger.info(f"📌 [{current_idx}/{total_todos}] 执行任务: {todo.task_type} - {todo.description}")
                logger.info(f"   重试次数: {todo.retry_count}/{todo.max_retries}")
                
                todo.status = "running"
                
                # 执行 TODO
                result = await self._execute_todo(
                    todo=todo,
                    task_plan=task_plan,
                    agent_mode=agent_mode,
                    wisdom=wisdom,
                    mode_plan=mode_plan,
                    workflow_dir=workflow_dir,
                    runtime=runtime
                )
                
                results.append(result)
                
                # 验证结果并处理重试逻辑
                verification_passed = True
                
                if todo.task_type == "plan_mode":
                    # 验证规划结果
                    from app.models.task import ModePlan
                    mode_plan_data = result.data.get("mode_plan") if result.data else None
                    
                    # 🔍 [DEBUG] 查看规划结果
                    logger.info(f"🔍 [DEBUG] plan_mode 结果:")
                    logger.info(f"🔍 [DEBUG]   result.success: {result.success}")
                    logger.info(f"🔍 [DEBUG]   result.data keys: {list(result.data.keys()) if result.data else 'None'}")
                    logger.info(f"🔍 [DEBUG]   mode_plan_data: {str(mode_plan_data)[:300] if mode_plan_data else 'None'}...")
                    
                    # 🔍 [DEBUG] 检查 mode_plan_data 中的 components 字段
                    if mode_plan_data and isinstance(mode_plan_data, dict):
                        logger.info(f"🔍 [DEBUG]   mode_plan_data 是字典，检查 components 字段:")
                        logger.info(f"🔍 [DEBUG]     mode_plan_data keys: {list(mode_plan_data.keys())}")
                        if "components" in mode_plan_data:
                            components = mode_plan_data.get("components", [])
                            logger.info(f"🔍 [DEBUG]     ✅ components 字段存在: type={type(components).__name__}, len={len(components) if isinstance(components, list) else 'N/A'}")
                            if components:
                                logger.info(f"🔍 [DEBUG]     components 内容: {components[:2] if len(components) > 2 else components}...")
                            else:
                                logger.warning(f"🔍 [DEBUG]     ⚠️ components 字段存在但为空列表!")
                        else:
                            logger.error(f"🔍 [DEBUG]     ❌ components 字段不存在于 mode_plan_data 中!")
                    
                    if mode_plan_data:
                        from app.models.task import WorkflowPlan, ReActPlan, MultiAgentPlan
                        # 根据 agent_mode 创建对应的 Plan 对象
                        if agent_mode == AgentMode.WORKFLOW:
                            mode_plan = WorkflowPlan(**mode_plan_data)
                            logger.info(f"🔍 [DEBUG]   WorkflowPlan 解析成功: files={mode_plan.files}, components={len(mode_plan.components)}")
                        elif agent_mode == AgentMode.REACT:
                            mode_plan = ReActPlan(**mode_plan_data)
                            logger.info(f"🔍 [DEBUG]   ReActPlan 解析成功: files={mode_plan.files}")
                        elif agent_mode == AgentMode.MULTI_AGENT:
                            mode_plan = MultiAgentPlan(**mode_plan_data)
                            logger.info(f"🔍 [DEBUG]   MultiAgentPlan 解析成功: files={mode_plan.files}")
                        else:
                            mode_plan = ModePlan(**mode_plan_data)
                            logger.info(f"🔍 [DEBUG]   ModePlan 解析成功: files={mode_plan.files}")
                    else:
                        logger.warning(f"🔍 [DEBUG]   ⚠️ mode_plan_data 为 None!")
                    
                    verifier = ResultVerifier(workflow_dir)
                    verification = verifier.verify_plan_result(result, agent_mode_str)
                    verification_passed = verification.passed
                    if not verification_passed:
                        logger.warning(f"⚠️ 规划验证失败: {verification.diff}")
                
                elif todo.task_type == "generate":
                    # 验证生成结果
                    if mode_plan:
                        verifier = ResultVerifier(workflow_dir)
                        verification = verifier.verify_generation_result(result, mode_plan)
                        verification_passed = verification.passed
                        if not verification_passed:
                            logger.warning(f"⚠️ 生成验证失败: {verification.diff}")
                        else:
                            # 验证通过后，保存生成的文件
                            files = result.data.get("files", {}) if result.data else {}
                            if files and workflow_dir:
                                self._save_generated_files(files, workflow_dir)
                                logger.info(f"💾 验证通过，已保存 {len(files)} 个文件到 {workflow_dir}")
                
                elif todo.task_type == "test":
                    # 验证测试结果
                    verifier = ResultVerifier(workflow_dir)
                    verification = verifier.verify_test_result(result)
                    verification_passed = verification.passed
                    if not verification_passed:
                        logger.warning(f"⚠️ 测试验证失败: {verification.diff}")
                        
                        # 如果测试失败，动态添加修复任务（场景2：执行失败修复）
                        error_info = {
                            "test_output": result.data.get("test_output", "") if result.data else "",
                            "errors": result.data.get("errors", "") if result.data else "",
                            "failed_tests": result.data.get("failed_tests", []) if result.data else [],
                            "test_command": result.data.get("command", "") if result.data else ""
                        }
                        
                        # 读取当前所有文件
                        all_files = {}
                        workflow_path = Path(workflow_dir)
                        for py_file in workflow_path.glob("*.py"):
                            try:
                                all_files[py_file.name] = py_file.read_text(encoding="utf-8")
                            except Exception as e:
                                logger.warning(f"读取文件失败 {py_file.name}: {e}")
                        
                        # 判断是场景1（用户修改）还是场景2（执行失败修复）
                        is_modify_scenario, modify_test_cycle_count, fix_test_cycle_count = \
                            self._extract_cycle_counts_from_todo(todo)
                        
                        # 动态添加修复任务
                        self._add_fix_errors_task(
                            task_plan=task_plan,
                            error_info=error_info,
                            workflow_dir=workflow_dir,
                            files=all_files,
                            fix_test_cycle_count=0 if is_modify_scenario else fix_test_cycle_count,
                            modify_test_cycle_count=modify_test_cycle_count if is_modify_scenario else None
                        )
                        
                        scenario_name = "修改后" if is_modify_scenario else "修复后"
                        cycle_info = f"修改-测试循环: {modify_test_cycle_count}" if is_modify_scenario else f"修复-测试循环: {fix_test_cycle_count}"
                        logger.info(f"🔧 {scenario_name}测试失败，已添加修复任务（{cycle_info}）。错误信息: {error_info.get('errors', '未知错误')[:200]}")
                
                # 处理修复任务的结果（场景1和场景2）
                if todo.task_type == "fix_errors":
                    if verification_passed:
                        # 修复成功，保存修复后的文件
                        if result.success and result.data:
                            modified_files = result.data.get("modified_files", {})
                            all_files = result.data.get("all_files", {})
                            
                            # 保存所有修改后的文件
                            for file_name, modified_content in modified_files.items():
                                file_path = Path(workflow_dir) / file_name
                                file_path.write_text(modified_content, encoding="utf-8")
                                logger.info(f"💾 保存修复后的文件: {file_name}")
                            
                            logger.info(f"✅ 修复完成，已保存 {len(modified_files)} 个修改后的文件")
                            
                            # 修复后，自动添加测试任务
                            is_modify_scenario, modify_test_cycle_count, fix_test_cycle_count = \
                                self._extract_cycle_counts_from_todo(todo)
                            
                            # 从工作流目录推断 agent_mode（如果还没有）
                            if agent_mode is None:
                                agent_mode = _detect_agent_mode_from_workflow_dir(workflow_dir)
                            
                            self._add_test_task_after_fix_or_modify(
                                task_plan=task_plan,
                                agent_mode=agent_mode,
                                is_modify_scenario=is_modify_scenario,
                                modify_test_cycle_count=modify_test_cycle_count,
                                fix_test_cycle_count=fix_test_cycle_count
                            )
                
                # 处理验证结果
                if verification_passed:
                    task_plan.mark_current_completed()
                    logger.info(f"✅ [{current_idx}/{total_todos}] 任务完成: {todo.task_type}")
                    task_plan.advance()
                else:
                    # 检查是否可以重试
                    if task_plan.increment_retry():
                        logger.info(f"🔄 [{current_idx}/{total_todos}] 准备重试 ({todo.retry_count}/{todo.max_retries})")
                        # 不调用 advance()，继续执行当前 todo
                    else:
                        task_plan.mark_current_failed()
                        logger.error(f"❌ [{current_idx}/{total_todos}] 任务失败，已达最大重试次数")
                        # 继续执行下一个任务，不阻塞整个流程
                        task_plan.advance()
            
            # 统计结果
            completed = sum(1 for t in task_plan.todos if t.status == "completed")
            failed = sum(1 for t in task_plan.todos if t.status == "failed")
            logger.info(f"📈 执行完成: 成功 {completed}/{total_todos}, 失败 {failed}/{total_todos}, 迭代次数 {iteration_count}")
            
            # 阶段 5: 更新智慧
            if self.wisdom_manager:
                self.wisdom_manager.update_wisdom(workflow_name, results)
            
            # 返回最终结果
            return AgentResult.success_result(
                data={
                    "workflow_dir": workflow_dir,
                    "results": [r.to_dict() for r in results],
                    "stats": {
                        "total": total_todos,
                        "completed": completed,
                        "failed": failed,
                        "iterations": iteration_count
                    }
                }
            ).to_dict()
        
        except Exception as e:
            logger.error(f"❌ 主协调器执行失败: {e}", exc_info=True)
            return AgentResult.failure_result(error=str(e)).to_dict()
    
    async def stream(self, inputs: Dict, runtime: Runtime = None) -> AsyncIterator[Dict[str, Any]]:
        """
        实现 openJiuwen 的 stream 接口（SSE 流式响应）
        
        在执行过程中实时发送事件，包括：
        - plan_started: 规划开始
        - plan_completed: 规划完成（包含 steps）
        - step_started: 每个步骤开始
        - step_completed: 每个步骤完成
        - test_started: 测试开始
        - test_completed: 测试完成
        - build_completed: 构建完成
        """
        import time
        from datetime import datetime
        
        MAX_GLOBAL_ITERATIONS = 20
        iteration_count = 0
        generated_files = {}
        workflow_dir = None
        mode_plan = None
        plan_data = None
        
        try:
            # 检测是否为修改模式
            is_modification = inputs.get("is_modification", False)
            
            if is_modification:
                # 修改模式
                workflow_dir = inputs.get("workflow_dir", "")
                modification_request = inputs.get("modification_request", "")
                conversation_id = inputs.get("conversation_id")
                max_iterations = inputs.get("max_iterations", 3)
                
                if not workflow_dir:
                    raise ValueError("修改模式必须提供 workflow_dir")
                
                # 标准化工作流目录路径
                workflow_dir = _normalize_workflow_dir(workflow_dir)
                
                if not Path(workflow_dir).exists():
                    raise ValueError(f"工作流目录不存在: {workflow_dir}")
                
                # 提取工作流名称
                workflow_name = _extract_workflow_name(workflow_dir)
                
                # 修改流程中不发送 plan_started 事件，避免创建不必要的步骤
                # 直接开始规划修改任务
                
                # 阶段 1: 规划修改任务
                task_plan = await self._plan_modification_tasks(
                    workflow_dir=workflow_dir,
                    modification_request=modification_request,
                    conversation_id=conversation_id
                )
                total_todos = len(task_plan.todos)
                
                # 修改模式不需要 intent_gate 和 wisdom
                wisdom = None
                agent_mode = None
                
            else:
                # 生成模式（原有逻辑）
                user_input = inputs.get("user_input", "")
                agent_mode_str = inputs.get("agent_mode", "workflow")
                workflow_name = inputs.get("workflow_name", "default")
                
                # 规范化 agent_mode（向后兼容：将 "agent" 映射到 "react"）
                agent_mode_str = normalize_agent_mode(agent_mode_str)
                agent_mode = AgentMode(agent_mode_str)
                
                # 如果未提供 workflow_dir，根据日期和用户输入生成目录名
                if "workflow_dir" not in inputs or not inputs.get("workflow_dir"):
                    dir_name = _generate_workflow_dir_name(user_input)
                    workflow_dir = f"experiments/{dir_name}"
                    workflow_name = dir_name
                else:
                    workflow_dir = inputs.get("workflow_dir")
                
                # 标准化工作流目录路径
                workflow_dir = _normalize_workflow_dir(workflow_dir)
                
                # 确保目录存在
                Path(workflow_dir).mkdir(parents=True, exist_ok=True)
                
                # 发送 plan_started 事件
                yield {
                    "type": "plan_started",
                    "message": "开始规划",
                    "data": {"workflow_name": workflow_name, "agent_mode": agent_mode_str},
                    "timestamp": time.time()
                }
                
                # 阶段 0: 意图识别和代码库评估
                intent_type = await self._intent_gate(user_input)
                codebase_state = await self._assess_codebase(workflow_dir)
                
                # 读取智慧
                wisdom = self.wisdom_manager.read_wisdom(workflow_name)
                
                # 阶段 1: 任务规划（L0 TaskPlan）
                task_plan = await self._plan_tasks(user_input, codebase_state, agent_mode)
                total_todos = len(task_plan.todos)
            
            # 阶段 2-4: 执行任务并验证
            results = []
            
            while not task_plan.is_complete():
                iteration_count += 1
                if iteration_count > MAX_GLOBAL_ITERATIONS:
                    logger.error(f"❌ 达到最大迭代次数 ({MAX_GLOBAL_ITERATIONS})，强制终止")
                    break
                
                todo = task_plan.get_current_todo()
                if not todo:
                    logger.warning("⚠️ 获取当前 TODO 失败，终止循环")
                    break
                
                current_idx = task_plan.current_index + 1
                todo.status = "running"
                
                # 发送 step_started 事件
                # 注意：
                # - plan_mode 不需要发送 todo 级别的 step_started，因为已经有 plan_started 事件
                # - generate 类型会在后续单独为每个文件发送 step_started
                # - test 类型会在后续发送专门的 test_started 事件，不需要通用的 step_started
                # - analyze_and_modify 类型会在后续单独发送 step_started，不需要通用的 step_started
                step_id = f"{todo.task_type}_{current_idx}"
                step_name = todo.description
                if todo.task_type not in ["generate", "plan_mode", "test", "analyze_and_modify"]:
                    yield {
                        "type": "step_started",
                        "step_id": step_id,
                        "step_name": step_name,
                        "message": f"开始执行: {step_name}",
                        "data": {
                            "step": {
                                "step_id": step_id,
                                "step_name": step_name,
                                "step_type": todo.task_type,
                                "description": todo.description
                            }
                        },
                        "timestamp": time.time()
                    }
                
                # 执行 TODO（generate、test、analyze_and_modify 任务有特殊处理）
                if todo.task_type not in ["generate", "test", "analyze_and_modify"]:
                    # 对于规划步骤，先生成思考过程
                    thinking_context = None
                    if todo.task_type == "plan_mode":
                        # 生成思考提示词
                        thinking_prompt = self._build_thinking_prompt_for_plan(
                            user_input=task_plan.user_input,
                            agent_mode=agent_mode_str
                        )
                        
                        # 生成并流式输出思考过程（不等待完成，直接返回迭代器）
                        thinking_context_ref, thinking_events = await self._generate_and_stream_thinking(
                            thinking_prompt=thinking_prompt,
                            step_id="plan",
                            step_name="规划阶段",
                            runtime=runtime
                        )
                        
                        # 立即开始转发思考事件（流式输出）
                        async for event in thinking_events:
                            yield event
                        
                        # 等待思考任务完成，获取思考上下文
                        thinking_context = thinking_context_ref["value"]
                    
                    # 执行 TODO（传入思考上下文）
                    result = await self._execute_todo(
                        todo=todo,
                        task_plan=task_plan,
                        agent_mode=agent_mode,
                        wisdom=wisdom,
                        mode_plan=mode_plan,
                        workflow_dir=workflow_dir,
                        runtime=runtime,
                        thinking_context=thinking_context
                    )
                    results.append(result)
                
                # 处理规划结果
                if todo.task_type == "plan_mode":
                    mode_plan_data = result.data.get("mode_plan") if result.data else None
                    
                    if mode_plan_data:
                        # 创建 mode_plan 对象
                        mode_plan = _create_mode_plan(mode_plan_data, agent_mode)
                        
                        # 构建 plan_data 和 steps 用于 plan_completed 事件
                        plan_data = mode_plan_data.copy() if isinstance(mode_plan_data, dict) else mode_plan.model_dump()
                        
                        # 根据 mode_plan 生成 steps（使用描述性名称）
                        steps = []
                        if mode_plan:
                            from app.modes.base import get_mode_generator
                            generator = get_mode_generator(agent_mode.value)
                            if generator:
                                required_files = generator.get_required_files()
                                for idx, file_name in enumerate(required_files):
                                    display_name = _get_file_display_name(file_name, agent_mode_str)
                                    steps.append({
                                        "step_id": f"generate_{idx}",
                                        "step_name": display_name,
                                        "step_type": _get_step_type(file_name),
                                        "description": display_name
                                    })
                        
                        # 发送 plan_completed 事件（规划阶段和设计阶段合并，统称为规划阶段）
                        step_names = [step.get("step_name") for step in steps]
                        yield {
                            "type": "plan_completed",
                            "message": f"规划完成，共 {len(steps)} 个步骤",
                            "data": {
                                "plan": plan_data,
                                "steps": steps,
                                "agent_mode": agent_mode_str,
                                "design_summary": {
                                    "mode": agent_mode_str,
                                    "files_count": len(steps),
                                    "files": step_names
                                }
                            },
                            "timestamp": time.time()
                        }
                    
                    verifier = ResultVerifier(workflow_dir)
                    verification = verifier.verify_plan_result(result, agent_mode_str)
                    verification_passed = verification.passed
                    
                elif todo.task_type == "generate":
                    # 对于 generate 任务，使用事件队列来实时接收生成过程中的事件
                    event_queue = asyncio.Queue()
                    
                    # 创建任务来执行生成
                    async def execute_with_events():
                        return await self._execute_todo(
                            todo=todo,
                            task_plan=task_plan,
                            agent_mode=agent_mode,
                            wisdom=wisdom,
                            mode_plan=mode_plan,
                            workflow_dir=workflow_dir,
                            runtime=runtime,
                            event_queue=event_queue
                        )
                    
                    execute_task = asyncio.create_task(execute_with_events())
                    
                    # 转发事件队列中的事件
                    async for event in self._forward_event_queue(event_queue, execute_task):
                        yield event
                    
                    result = await execute_task
                    results.append(result)
                    
                    # 验证生成结果
                    if mode_plan:
                        verifier = ResultVerifier(workflow_dir)
                        verification = verifier.verify_generation_result(result, mode_plan)
                        verification_passed = verification.passed
                        
                        if not verification_passed:
                            logger.warning(f"⚠️ 生成验证失败: {verification.failure_type} - {verification.diff}")
                            logger.info(f"   当前重试次数: {todo.retry_count}/{todo.max_retries}")
                        
                        if verification_passed:
                            # 获取生成的文件
                            files = result.data.get("files", {}) if result.data else {}
                            if files:
                                generated_files.update(files)
                                self._save_generated_files(files, workflow_dir)
                                logger.info(f"✅ 生成验证通过，已保存 {len(files)} 个文件")
                    else:
                        # mode_plan 为 None，说明规划阶段失败，无法继续生成
                        logger.error("❌ mode_plan 为 None，无法验证生成结果。请先完成规划阶段。")
                        verification_passed = False
                        # 直接标记为失败，不重试（因为没有 mode_plan，重试也会失败）
                        task_plan.mark_current_failed()
                        yield {
                            "type": "step_failed",
                            "step_id": step_id,
                            "step_name": step_name,
                            "message": f"步骤失败: {step_name}（缺少 mode_plan）",
                            "data": {"error": "规划阶段未完成，无法生成代码"},
                            "timestamp": time.time()
                        }
                        task_plan.advance()
                        continue  # 跳过后续验证逻辑，直接进入下一个任务
                
                elif todo.task_type == "test":
                    # 判断是否是修复后的测试（通过检查 metadata）
                    is_post_fix_test = False
                    test_context = "生成的代码"
                    step_name = "测试阶段"
                    step_id = "test"
                    
                    if todo.metadata:
                        if 'modify_test_cycle_count' in todo.metadata:
                            is_post_fix_test = True
                            test_context = "修改后的代码"
                            modify_cycle = todo.metadata.get('modify_test_cycle_count', 0)
                            step_name = f"测试修改后的代码（第 {modify_cycle} 次）"
                            step_id = f"test_after_modify_{modify_cycle}"
                        elif 'fix_test_cycle_count' in todo.metadata:
                            is_post_fix_test = True
                            test_context = "修复后的代码"
                            fix_cycle = todo.metadata.get('fix_test_cycle_count', 0)
                            step_name = f"测试修复后的代码（第 {fix_cycle} 次）"
                            step_id = f"test_after_fix_{fix_cycle}"
                    
                    # 先发送 test_started 事件（在测试执行前）
                    yield {
                        "type": "test_started",
                        "step_id": step_id,
                        "step_name": step_name,
                        "message": f"开始测试{test_context}...",
                        "data": {
                            "is_post_fix_test": is_post_fix_test,
                            "test_context": test_context,
                            "step": {
                                "step_id": step_id,
                                "step_name": step_name,
                                "step_type": "test",
                                "description": f"测试{test_context}"
                            }
                        },
                        "timestamp": time.time()
                    }
                    
                    # ✅ 确保事件立即推送到前端：让出控制权给事件循环
                    await asyncio.sleep(0)
                    
                    # 执行测试任务
                    result = await self._execute_todo(
                        todo=todo,
                        task_plan=task_plan,
                        agent_mode=agent_mode,
                        wisdom=wisdom,
                        mode_plan=mode_plan,
                        workflow_dir=workflow_dir,
                        runtime=runtime
                    )
                    results.append(result)
                    
                    # 验证测试结果
                    verifier = ResultVerifier(workflow_dir)
                    verification = verifier.verify_test_result(result)
                    verification_passed = verification.passed
                    
                    # 构建标准化的测试结果数据
                    test_result_data = _build_test_result_data(result.data if result.data else {})
                    
                    # 发送测试完成事件
                    test_event_type = "test_completed" if verification_passed else "test_failed"
                    test_message = "测试通过！" if verification_passed else f"测试失败: {getattr(verification, 'diff', '未知错误')}"
                    
                    yield {
                        "type": test_event_type,
                        "step_id": step_id,
                        "step_name": step_name,
                        "message": test_message,
                        "data": {
                            "test_result": test_result_data,
                            "test_cases": test_result_data.get("test_cases", []),
                            "test_summary": test_result_data.get("test_output", ""),
                            "is_post_fix_test": is_post_fix_test,
                            "test_context": test_context,
                            "step": {
                                "step_id": step_id,
                                "step_name": step_name,
                                "step_type": "test",
                                "description": f"测试{test_context}"
                            }
                        },
                        "timestamp": time.time()
                    }
                    
                    # 如果测试失败，动态添加修复任务（场景2：执行失败修复）
                    if not verification_passed:
                        # 构建错误信息
                        error_info = {
                            "test_output": test_result_data.get("test_output", ""),
                            "errors": test_result_data.get("errors", ""),
                            "failed_tests": test_result_data.get("test_cases", []),
                            "test_command": test_result_data.get("command", "")
                        }
                        
                        # 读取当前所有文件
                        all_files = self._load_all_python_files(workflow_dir, generated_files)
                        
                        # 判断是场景1（用户修改）还是场景2（执行失败修复）
                        # 通过检查 todo.metadata 中是否有 modify_test_cycle_count 来判断
                        is_modify_scenario = False
                        modify_test_cycle_count = 0
                        fix_test_cycle_count = 0
                        
                        if todo.metadata:
                            # 场景1：用户修改后的测试失败
                            if 'modify_test_cycle_count' in todo.metadata:
                                is_modify_scenario = True
                                modify_test_cycle_count = todo.metadata.get('modify_test_cycle_count', 0)
                            # 场景2：执行失败修复后的测试失败
                            elif 'fix_test_cycle_count' in todo.metadata:
                                fix_test_cycle_count = todo.metadata.get('fix_test_cycle_count', 0)
                        
                        # 动态添加修复任务
                        if is_modify_scenario:
                            # 场景1：用户修改后的测试失败，使用修改-测试循环次数
                            self._add_fix_errors_task(
                                task_plan=task_plan,
                                error_info=error_info,
                                workflow_dir=workflow_dir,
                                files=all_files,
                                fix_test_cycle_count=0,  # 修复任务从0开始计数
                                modify_test_cycle_count=modify_test_cycle_count  # 传递修改-测试循环次数
                            )
                            logger.info(f"🔧 修改后测试失败，已添加修复任务（修改-测试循环: {modify_test_cycle_count}）。错误信息: {error_info.get('errors', '未知错误')[:200]}")
                        else:
                            # 场景2：执行失败修复后的测试失败
                            self._add_fix_errors_task(
                                task_plan=task_plan,
                                error_info=error_info,
                                workflow_dir=workflow_dir,
                                files=all_files,
                                fix_test_cycle_count=fix_test_cycle_count
                            )
                            logger.info(f"🔧 修复后测试失败，已添加修复任务（修复-测试循环: {fix_test_cycle_count}）。错误信息: {error_info.get('errors', '未知错误')[:200]}")
                elif todo.task_type == "analyze_and_modify":
                    # 分析并修改（合并流程）
                    event_queue = asyncio.Queue()
                    modification_request = inputs.get("modification_request", "")
                    
                    # 创建任务来执行分析和修改
                    async def execute_analyze_and_modify_with_events():
                        return await self._execute_todo(
                            todo=todo,
                            task_plan=task_plan,
                            agent_mode=None,
                            wisdom=None,
                            mode_plan=None,
                            workflow_dir=workflow_dir,
                            runtime=runtime,
                            event_queue=event_queue,
                            modification_request=modification_request,
                            conversation_id=inputs.get("conversation_id")
                        )
                    
                    execute_task = asyncio.create_task(execute_analyze_and_modify_with_events())
                    
                    # 转发事件队列中的事件（包括分析步骤和每个文件的修改步骤）
                    async for event in self._forward_event_queue(event_queue, execute_task):
                        yield event
                    
                    result = await execute_task
                    results.append(result)
                    
                    # 处理结果：保存修改后的文件
                    if result.success and result.data:
                        modified_files = result.data.get("modified_files", {})
                        files_to_modify = result.data.get("files_to_modify", [])
                        modification_plan = result.data.get("modification_plan", {})
                        all_files = result.data.get("all_files", {})
                        all_requirements = result.data.get("all_requirements", [])
                        components = result.data.get("components", [])
                        workflow_structure = result.data.get("workflow_structure", {})
                        
                        # 保存所有修改后的文件
                        for file_name, modified_content in modified_files.items():
                            self._save_modified_file(
                                file_name=file_name,
                                content=modified_content,
                                workflow_dir=workflow_dir,
                                generated_files=generated_files
                            )
                            # 更新 all_files 中的文件内容
                            all_files[file_name] = modified_content
                        
                        # 重要：更新 task_plan 的 metadata，确保 all_files 包含所有文件（包括未修改的）
                        # 这样在 build_completed 事件中才能正确获取所有文件
                        self._set_modification_metadata(
                            task_plan=task_plan,
                            files_to_modify=files_to_modify,
                            modification_plan=modification_plan,
                            all_files=all_files,  # 包含所有文件（修改后的和未修改的）
                            all_requirements=all_requirements,
                            components=components,
                            workflow_structure=workflow_structure
                        )
                        
                        logger.info(f"✅ 更新 modification_metadata，all_files 包含 {len(all_files)} 个文件: {sorted(all_files.keys())}")
                        
                        # 发送 plan_completed 事件（包含所有步骤信息）
                        yield {
                            "type": "plan_completed",
                            "title": "修改工作流完成",
                            "message": f"修改完成，共修改 {len(modified_files)} 个文件",
                            "data": {
                                "files_to_modify": files_to_modify,
                                "modified_files": list(modified_files.keys()),
                                "modification_plan": modification_plan,
                                "components": components,
                                "workflow_structure": workflow_structure,
                                "all_files": all_files,  # 也包含在 plan_completed 事件中，供前端使用
                                "steps": [
                                    {
                                        "step_id": "analyze_modification",
                                        "step_name": "分析修改需求",
                                        "step_type": "analyze_modification",
                                        "description": "分析修改需求，确定需要修改的文件"
                                    }
                                ] + [
                                    {
                                        "step_id": f"modify_{file_name.replace('.', '_')}",
                                        "step_name": f"修改 {file_name}",
                                        "step_type": "modify_file",
                                        "description": modification_plan.get(file_name, f"修改 {file_name}")
                                    }
                                    for file_name in files_to_modify
                                ]
                            },
                            "timestamp": time.time()
                        }
                        
                        # 修改完成后，自动添加测试任务（场景1：用户增量修改）
                        # 从工作流目录推断 agent_mode
                        detected_agent_mode = _detect_agent_mode_from_workflow_dir(workflow_dir)
                        
                        if detected_agent_mode:
                            # 设置最大修改-测试循环次数（防止无限循环）
                            MAX_MODIFY_TEST_CYCLES = 3
                            
                            # 修改-测试循环次数从 0 开始（第一次修改后的测试）
                            modify_test_cycle_count = 0
                            
                            # 动态添加测试任务
                            self._add_test_task_after_modify(
                                task_plan=task_plan,
                                agent_mode=detected_agent_mode,
                                modify_test_cycle_count=modify_test_cycle_count
                            )
                            
                            logger.info(f"🔄 修改完成，已添加测试任务（修改-测试循环: {modify_test_cycle_count + 1}/{MAX_MODIFY_TEST_CYCLES}）")
                        else:
                            logger.warning(f"⚠️ 无法从工作流目录推断 agent_mode，跳过自动测试")
                    
                    verification_passed = result.success if result else False
                
                elif todo.task_type == "fix_errors":
                    # 修复错误任务（场景2：执行失败修复）
                    event_queue = asyncio.Queue()
                    
                    # 从 todo 的 metadata 中获取错误信息
                    error_info = todo.metadata.get('error_info', {}) if todo.metadata else {}
                    files = todo.metadata.get('files', {}) if todo.metadata else {}
                    
                    # 创建任务来执行修复
                    async def execute_fix_errors_with_events():
                        return await self._execute_todo(
                            todo=todo,
                            task_plan=task_plan,
                            agent_mode=agent_mode,
                            wisdom=wisdom,
                            mode_plan=mode_plan,
                            workflow_dir=workflow_dir,
                            runtime=runtime,
                            event_queue=event_queue
                        )
                    
                    execute_task = asyncio.create_task(execute_fix_errors_with_events())
                    
                    # 转发事件队列中的事件
                    async for event in self._forward_event_queue(event_queue, execute_task):
                        yield event
                    
                    result = await execute_task
                    results.append(result)
                    
                    # 处理结果：保存修复后的文件
                    if result.success and result.data:
                        modified_files = result.data.get("modified_files", {})
                        all_files = result.data.get("all_files", {})
                        
                        # 保存所有修改后的文件
                        for file_name, modified_content in modified_files.items():
                            self._save_modified_file(
                                file_name=file_name,
                                content=modified_content,
                                workflow_dir=workflow_dir,
                                generated_files=generated_files
                            )
                            # 更新 generated_files
                            generated_files[file_name] = modified_content
                        
                        # 如果 all_files 中有未修改的文件，也更新 generated_files
                        if all_files:
                            for file_name, file_content in all_files.items():
                                if file_name not in generated_files:
                                    generated_files[file_name] = file_content
                        
                        logger.info(f"✅ 修复完成，已保存 {len(modified_files)} 个修改后的文件")
                        
                        # 修复后，自动添加测试任务（修复-测试循环）
                        # 获取当前的修复-测试循环次数和修改-测试循环次数
                        fix_test_cycle_count = 0
                        modify_test_cycle_count = None
                        is_modify_scenario = False
                        
                        if todo.metadata:
                            fix_test_cycle_count = todo.metadata.get('fix_test_cycle_count', 0)
                            # 检查是否是场景1（用户修改）
                            if 'modify_test_cycle_count' in todo.metadata:
                                is_modify_scenario = True
                                modify_test_cycle_count = todo.metadata.get('modify_test_cycle_count', 0)
                        
                        # 设置最大循环次数（防止无限循环）
                        MAX_FIX_TEST_CYCLES = 3
                        MAX_MODIFY_TEST_CYCLES = 3
                        
                        # 判断是否达到上限
                        should_add_test = False
                        if is_modify_scenario:
                            # 场景1：检查修改-测试循环次数
                            if modify_test_cycle_count is not None and modify_test_cycle_count < MAX_MODIFY_TEST_CYCLES:
                                should_add_test = True
                                modify_test_cycle_count += 1
                        else:
                            # 场景2：检查修复-测试循环次数
                            if fix_test_cycle_count < MAX_FIX_TEST_CYCLES:
                                should_add_test = True
                                fix_test_cycle_count += 1
                        
                        if should_add_test:
                            # 从工作流目录推断 agent_mode（如果还没有）
                            if agent_mode is None:
                                agent_mode = _detect_agent_mode_from_workflow_dir(workflow_dir)
                            
                            if agent_mode:
                                if is_modify_scenario:
                                    # 场景1：使用修改-测试循环
                                    self._add_test_task_after_modify(
                                        task_plan=task_plan,
                                        agent_mode=agent_mode,
                                        modify_test_cycle_count=modify_test_cycle_count
                                    )
                                    logger.info(f"🔄 修复完成，已添加测试任务（修改-测试循环: {modify_test_cycle_count}/{MAX_MODIFY_TEST_CYCLES}）")
                                else:
                                    # 场景2：使用修复-测试循环
                                    self._add_test_task_after_fix(
                                        task_plan=task_plan,
                                        agent_mode=agent_mode,
                                        fix_test_cycle_count=fix_test_cycle_count
                                    )
                                    logger.info(f"🔄 修复完成，已添加测试任务（修复-测试循环: {fix_test_cycle_count}/{MAX_FIX_TEST_CYCLES}）")
                            else:
                                logger.warning(f"⚠️ 无法推断 agent_mode，跳过自动测试")
                        else:
                            max_cycles = MAX_MODIFY_TEST_CYCLES if is_modify_scenario else MAX_FIX_TEST_CYCLES
                            logger.warning(f"⚠️ 已达到最大循环次数 ({max_cycles})，不再自动添加测试任务")
                    
                    verification_passed = result.success if result else False
                
                elif todo.task_type == "modify_file":
                    # 修改文件任务
                    event_queue = asyncio.Queue()
                    
                    # 从 task_plan 的 metadata 中获取文件信息
                    modification_metadata = self._get_modification_metadata(task_plan)
                    all_files = modification_metadata.get("all_files", {})
                    all_requirements = modification_metadata.get("all_requirements", [])
                    
                    # 确定要修改的文件
                    file_to_modify = self._get_file_to_modify(todo, task_plan)
                    if not file_to_modify:
                        logger.error("无法确定要修改的文件")
                        verification_passed = False
                        task_plan.advance()
                        continue
                    
                    # 加载文件内容
                    file_content = self._load_file_content(file_to_modify, workflow_dir, all_files)
                    if not file_content:
                        logger.error(f"文件不存在或无法读取: {file_to_modify}")
                        verification_passed = False
                        task_plan.advance()
                        continue
                    
                    # 发送 step_started 事件（在思考过程之前）
                    step_id = f"modify_{file_to_modify.replace('.', '_')}"
                    step_name = f"修改 {file_to_modify}"
                    yield {
                        "type": "step_started",
                        "step_id": step_id,
                        "step_name": step_name,
                        "message": f"开始执行: {step_name}",
                        "data": {
                            "step": {
                                "step_id": step_id,
                                "step_name": step_name,
                                "step_type": "modify_file",
                                "description": step_name
                            }
                        },
                        "timestamp": time.time()
                    }
                    
                    # 从 metadata 中获取新的工作流结构
                    new_components = modification_metadata.get("components", [])
                    new_workflow_structure = modification_metadata.get("workflow_structure", {})
                    
                    # 创建任务来执行修改
                    async def execute_modify_with_events():
                        return await self._execute_todo(
                            todo=todo,
                            task_plan=task_plan,
                            agent_mode=None,
                            wisdom=None,
                            mode_plan=None,
                            workflow_dir=workflow_dir,
                            runtime=runtime,
                            event_queue=event_queue,
                            modification_request=inputs.get("modification_request", ""),
                            file_path=file_to_modify,
                            file_content=file_content,
                            all_requirements=all_requirements,
                            all_files=all_files,
                            components=new_components,
                            workflow_structure=new_workflow_structure
                        )
                    
                    execute_task = asyncio.create_task(execute_modify_with_events())
                    
                    # 转发事件队列中的事件
                    async for event in self._forward_event_queue(event_queue, execute_task):
                        yield event
                    
                    result = await execute_task
                    results.append(result)
                    
                    # 保存修改后的文件
                    if result.success and result.data:
                        modified_content = result.data.get("modified_content", "")
                        if modified_content:
                            self._save_modified_file(
                                file_name=file_to_modify,
                                content=modified_content,
                                workflow_dir=workflow_dir,
                                generated_files=generated_files
                            )
                            # 更新 all_files 中的文件内容（确保后续步骤能获取最新内容）
                            all_files[file_to_modify] = modified_content
                    
                    verification_passed = result.success if result else False
                
                else:
                    verification_passed = True
                
                # 处理验证结果
                if verification_passed:
                    task_plan.mark_current_completed()
                    if todo.task_type != "plan_mode" and todo.task_type != "test":
                        # 对于非规划和非测试步骤，发送 step_completed（如果还没发送）
                        if todo.task_type != "generate":  # generate 已经发送了
                            yield {
                                "type": "step_completed",
                                "step_id": step_id,
                                "step_name": step_name,
                                "message": f"步骤完成: {step_name}",
                                "data": {"result": result.to_dict() if hasattr(result, 'to_dict') else {}},
                                "timestamp": time.time()
                            }
                    task_plan.advance()
                else:
                    if task_plan.increment_retry():
                        logger.info(f"🔄 [{current_idx}/{total_todos}] 准备重试 ({todo.retry_count}/{todo.max_retries})")
                    else:
                        task_plan.mark_current_failed()
                        yield {
                            "type": "step_failed",
                            "step_id": step_id,
                            "step_name": step_name,
                            "message": f"步骤失败: {step_name}",
                            "data": {"error": result.error if hasattr(result, 'error') else "未知错误"},
                            "timestamp": time.time()
                        }
                        task_plan.advance()
            
            # 统计结果
            completed = sum(1 for t in task_plan.todos if t.status == "completed")
            failed = sum(1 for t in task_plan.todos if t.status == "failed")
            
            # 阶段 5: 更新智慧
            if self.wisdom_manager:
                self.wisdom_manager.update_wisdom(workflow_name, results)
            
            # 计算相对路径（用于前端）
            project_root = Path(__file__).parent.parent.parent.parent
            if workflow_dir.startswith(str(project_root)):
                saved_directory = workflow_dir[len(str(project_root)) + 1:].replace("\\", "/")
            else:
                saved_directory = workflow_dir.replace("\\", "/")
            
            # 如果是修改模式，确保返回所有文件（包括未修改的）
            if is_modification:
                # 从 metadata 中获取所有文件
                modification_metadata = self._get_modification_metadata(task_plan) if hasattr(task_plan, '_modification_metadata') else {}
                all_files = modification_metadata.get("all_files", {})
                
                logger.info(f"📋 [build_completed] 修改模式：从 metadata 获取 all_files，包含 {len(all_files)} 个文件: {sorted(all_files.keys())}")
                logger.info(f"📋 [build_completed] 修改模式：generated_files 当前包含 {len(generated_files)} 个文件: {sorted(generated_files.keys())}")
                
                # 合并生成的文件和所有文件（确保未修改的文件也被包含）
                for file_name, file_content in all_files.items():
                    if file_name not in generated_files:
                        generated_files[file_name] = file_content
                        logger.info(f"✅ [build_completed] 补充文件到 generated_files: {file_name}")
                
                logger.info(f"📋 [build_completed] 修改模式：最终 generated_files 包含 {len(generated_files)} 个文件: {sorted(generated_files.keys())}")
            
            # 发送 build_completed 事件
            yield {
                "type": "build_completed",
                "message": "构建完成",
                "data": {
                    "saved_directory": saved_directory,
                    "generated_files": generated_files,
                    "plan": plan_data or {},
                    "workflow_dir": workflow_dir,
                    "stats": {
                        "total": total_todos,
                        "completed": completed,
                        "failed": failed,
                        "iterations": iteration_count
                    }
                },
                "timestamp": time.time()
            }
        
        except Exception as e:
            logger.error(f"❌ 主协调器执行失败: {e}", exc_info=True)
            yield {
                "type": "build_failed",
                "message": f"构建失败: {str(e)}",
                "data": {"error": str(e)},
                "timestamp": time.time()
            }
    
    async def _intent_gate(self, user_input: str) -> IntentType:
        """
        意图识别
        
        Args:
            user_input: 用户输入
        
        Returns:
            意图类型
        """
        # 简单启发式判断：词数少于20为简单，否则为复杂
        word_count = len(user_input.split())
        if word_count < 20:
            return IntentType.SIMPLE
        else:
            return IntentType.COMPLEX
    
    async def _assess_codebase(self, workflow_dir: str) -> CodebaseState:
        """
        代码库评估
        
        Args:
            workflow_dir: 工作流目录
        
        Returns:
            代码库状态
        """
        workflow_path = Path(workflow_dir)
        
        if not workflow_path.exists():
            return CodebaseState.GREENFIELD
        
        # 检查是否有现有 Python 文件
        py_files = list(workflow_path.glob("*.py"))
        if not py_files:
            return CodebaseState.GREENFIELD
        else:
            return CodebaseState.LEGACY
    
    async def _plan_modification_tasks(
        self,
        workflow_dir: str,
        modification_request: str,
        conversation_id: Optional[str] = None
    ) -> TaskPlan:
        """
        规划修改任务
        
        Args:
            workflow_dir: 工作流目录
            modification_request: 修改需求
            conversation_id: 会话ID（用于获取历史）
        
        Returns:
            TaskPlan 实例（包含 analyze_modification 和 modify_file 任务）
        """
        todos = []
        
        # 第一步：分析并修改（合并为一个任务）
        todos.append(TodoItem(
            task_type="analyze_and_modify",
            description="分析修改需求并修改所有文件",
            mode=None,
            category=None,
            skills=[],
            expected_files=[],
            expected_outcome="完成所有文件的修改",
            max_retries=1
        ))
        
        return TaskPlan(
            todos=todos,
            current_index=0,
            user_input=modification_request,
            agent_mode=None  # 修改模式不指定 agent_mode
        )
    
    async def _plan_tasks(
        self,
        user_input: str,
        codebase_state: CodebaseState,
        agent_mode: AgentMode
    ) -> TaskPlan:
        """
        任务规划（L0：TaskPlan）
        
        Args:
            user_input: 用户输入
            codebase_state: 代码库状态
            agent_mode: Agent 模式
        
        Returns:
            TaskPlan 实例
        """
        todos = []
        
        # 标准流程：生成详细计划 → 生成代码 → 测试 → 修复（可选）
        todos.append(TodoItem(
            task_type="plan_mode",
            description="生成详细的模式计划（ModePlan）",
            mode=agent_mode,
            category=None,
            skills=[],
            expected_files=[],
            expected_outcome="生成包含具体生成步骤的 ModePlan"
        ))
        
        todos.append(TodoItem(
            task_type="generate",
            description=f"根据 ModePlan 生成 {agent_mode.value} 模式代码",
            mode=agent_mode,
            category="coder",
            skills=self._get_skills_for_mode(agent_mode),
            expected_files=self._get_expected_files(agent_mode),
            expected_outcome="生成所有必需的文件"
        ))
        
        todos.append(TodoItem(
            task_type="test",
            description="测试生成的代码",
            mode=agent_mode,
            category=None,
            skills=[],
            expected_files=[],
            expected_outcome="所有测试通过"
        ))
        
        # 如果是遗留项目，添加修复步骤
        if codebase_state == CodebaseState.LEGACY:
            todos.append(TodoItem(
                task_type="fix",
                description="修复可能的兼容性问题",
                mode=agent_mode,
                category=None,
                skills=[],
                expected_files=[],
                expected_outcome="修复所有错误"
            ))
        
        return TaskPlan(
            todos=todos,
            current_index=0,
            user_input=user_input,
            agent_mode=agent_mode
        )
    
    async def _execute_todo(
        self,
        todo: TodoItem,
        task_plan: TaskPlan,
        agent_mode: Optional[AgentMode],
        wisdom: Any,
        mode_plan: Optional[ModePlan],
        workflow_dir: str,
        runtime: Runtime,
        event_queue: Optional[Any] = None,
        thinking_context: Optional[str] = None,
        modification_request: Optional[str] = None,
        conversation_id: Optional[str] = None,
        file_path: Optional[str] = None,
        file_content: Optional[str] = None,
        all_requirements: Optional[List[str]] = None,
        all_files: Optional[Dict[str, str]] = None
    ) -> AgentResult:
        """
        执行 TODO 项
        
        Args:
            todo: TODO 项
            task_plan: 任务计划
            agent_mode: Agent 模式
            wisdom: 智慧数据
            mode_plan: 模式计划（如果已生成）
            workflow_dir: 工作流目录
            runtime: Runtime 实例
        
        Returns:
            执行结果
        """
        # 构建委托提示词（包含思考上下文）
        prompt = self._build_delegation_prompt(todo, task_plan, wisdom, mode_plan, thinking_context)
        
        # 根据 TODO 类型选择委托方式
        if todo.task_type == "plan_mode":
            # 委托给 PlannerAgent
            planner_inputs = {
                "agent_type": "planner",
                "prompt": prompt
            }
            # 传递 agent_mode（如果存在）
            if agent_mode:
                planner_inputs["agent_mode"] = agent_mode.value
            result_dict = await self.delegation_tool.ainvoke(
                inputs=planner_inputs,
                runtime=runtime
            )
        elif todo.task_type == "generate":
            # 委托给动态执行器（类别模式）
            inputs_dict = {
                "category": todo.category or "coder",
                "prompt": prompt,
                "skills": todo.skills,
                "include_references": mode_plan.include_references if mode_plan else None,
                "token_budget": mode_plan.token_budget if mode_plan else None,
                "agent_mode": agent_mode.value,
                "mode_plan": mode_plan.model_dump(exclude_none=False, exclude_unset=False) if mode_plan else None,
                "workflow_dir": workflow_dir
            }
            # 如果有事件队列，传递给它
            if event_queue is not None:
                inputs_dict["_event_queue"] = event_queue
            
            result_dict = await self.delegation_tool.ainvoke(
                inputs=inputs_dict,
                runtime=runtime
            )
        elif todo.task_type == "test":
            # 委托给 TesterAgent
            tester_inputs = {
                "agent_type": "tester",
                "prompt": prompt,
                "workflow_dir": workflow_dir
            }
            # 传递 agent_mode 给 TesterAgent（用于 multi-agent 模式的特殊测试处理）
            if agent_mode:
                tester_inputs["agent_mode"] = agent_mode.value if hasattr(agent_mode, 'value') else str(agent_mode)
            # 传递 mode_plan 给 TesterAgent（用于获取测试查询等信息）
            if mode_plan:
                tester_inputs["mode_plan"] = mode_plan.model_dump(exclude_none=False, exclude_unset=False)
            # 传递 smoke_tests 给 TesterAgent（如果 mode_plan 中有）
            if mode_plan and hasattr(mode_plan, 'smoke_tests') and mode_plan.smoke_tests:
                tester_inputs["smoke_tests"] = mode_plan.smoke_tests
            # 传递事件队列给 TesterAgent（用于发送进度事件）
            if event_queue is not None:
                tester_inputs["_event_queue"] = event_queue
            result_dict = await self.delegation_tool.ainvoke(
                inputs=tester_inputs,
                runtime=runtime
            )
        elif todo.task_type == "fix":
            # 委托给 FixerAgent（保留用于兼容旧版本）
            result_dict = await self.delegation_tool.ainvoke(
                inputs={
                    "agent_type": "fixer",
                    "prompt": prompt
                },
                runtime=runtime
            )
        elif todo.task_type == "fix_errors":
            # 委托给 FixerAgent 修复错误（场景2：执行失败修复）
            # 从 todo 的 metadata 中获取错误信息
            error_info = {}
            workflow_dir_for_fix = workflow_dir
            files = {}
            
            if todo.metadata:
                error_info = todo.metadata.get('error_info', {})
                workflow_dir_for_fix = todo.metadata.get('workflow_dir', workflow_dir)
                files = todo.metadata.get('files', {})
            else:
                error_info = {}
                workflow_dir_for_fix = workflow_dir
                files = {}
            
            result_dict = await self.delegation_tool.ainvoke(
                inputs={
                    "agent_type": "fixer",
                    "task_type": "fix_errors",
                    "workflow_dir": workflow_dir_for_fix,
                    "error_info": error_info,
                    "files": files,
                    "_event_queue": event_queue
                },
                runtime=runtime
            )
        elif todo.task_type == "analyze_and_modify":
            # 委托给 FixerAgent 进行分析和修改（合并流程）
            result_dict = await self.delegation_tool.ainvoke(
                inputs={
                    "agent_type": "fixer",
                    "task_type": "analyze_and_modify",
                    "prompt": prompt,
                    "workflow_dir": workflow_dir,
                    "modification_request": modification_request or "",
                    "conversation_id": conversation_id,
                    "_event_queue": event_queue
                },
                runtime=runtime
            )
        elif todo.task_type == "analyze_modification":
            # 委托给 FixerAgent 进行分析（保留用于兼容）
            result_dict = await self.delegation_tool.ainvoke(
                inputs={
                    "agent_type": "fixer",
                    "task_type": "analyze_modification",
                    "prompt": prompt,
                    "workflow_dir": workflow_dir,
                    "modification_request": modification_request or "",
                    "conversation_id": conversation_id
                },
                runtime=runtime
            )
        elif todo.task_type == "modify_file":
            # 委托给 FixerAgent 进行文件修改
            # 从 metadata 中获取新的工作流结构（如果存在）
            modification_metadata = self._get_modification_metadata(task_plan)
            new_components = modification_metadata.get("components", [])
            new_workflow_structure = modification_metadata.get("workflow_structure", {})
            
            result_dict = await self.delegation_tool.ainvoke(
                inputs={
                    "agent_type": "fixer",
                    "task_type": "modify_file",
                    "prompt": prompt,
                    "workflow_dir": workflow_dir,
                    "modification_request": modification_request or "",
                    "file_path": file_path or "",
                    "file_content": file_content or "",
                    "all_requirements": all_requirements or [],
                    "all_files": all_files or {},
                    "components": new_components,  # 传递新的组件列表
                    "workflow_structure": new_workflow_structure,  # 传递新的工作流结构
                    "_event_queue": event_queue
                },
                runtime=runtime
            )
        else:
            return AgentResult.failure_result(error=f"未知的任务类型: {todo.task_type}")
        
        return AgentResult(**result_dict)
    
    def _load_skill_reference(self, skill_name: str, ref_name: str, max_length: int = 2000) -> str:
        """加载 skill 参考文档"""
        skills_dir = Path(__file__).parent.parent.parent / "skills"
        ref_path = skills_dir / skill_name / "references" / ref_name
        if not ref_path.exists():
            return ""
        content = ref_path.read_text(encoding="utf-8")
        return content[:max_length] + "\n...（已截断）" if len(content) > max_length else content
    
    def _build_thinking_prompt_for_analysis(self, modification_request: str) -> str:
        """
        构建分析修改需求的思考提示词
        
        Args:
            modification_request: 修改需求
        
        Returns:
            思考提示词
        """
        return f"""## 修改需求分析

当前修改需求: {modification_request}

## 任务
作为资深程序员，用口语化方式思考这个修改需求该如何实现。

要求：
- 200-300字左右
- 口语化，像自言自语："嗯，用户想要..."、"让我看看..."、"需要..."、"关键是要..."
- 分析：需要改哪些文件、为什么、怎么改

开始思考："""
    
    def _build_thinking_prompt_for_plan(
        self,
        user_input: str,
        agent_mode: str
    ) -> str:
        """构建规划步骤的思考提示词（口语化、模拟真实思考，包含实际 skill 信息）"""
        skill_name = self.SKILL_NAME_MAP.get(agent_mode, "workflow-generation-skill")
        plan_schema = self._load_skill_reference(skill_name, "plan-schema.md", max_length=2000)
        mode_hint = self.MODE_HINTS.get(agent_mode, "需要分析组件和逻辑结构")
        
        schema_section = f"\n## 规划规范（参考此规范进行思考）\n{plan_schema}\n\n" if plan_schema else ""
        
        return f"""## 用户需求
{user_input}

## 模式
{agent_mode}（{mode_hint}）{schema_section}## 思考任务
作为一个资深架构师，用第一人称口语化的方式思考这个需求该怎么实现。**必须参考上面的规划规范**。

要求：
- 250-350字左右
- 口语化，像自言自语："嗯，这个需求..."、"让我想想..."、"根据规范..."、"关键点是..."、"然后呢..."
- **要结合规划规范思考**：需要哪些文件、组件结构、关键符号、技能依赖等
- 要分析：核心功能是什么、需要哪些组件/工具、数据怎么流转、有什么注意点
- 最后给出简要的实现思路

示例风格：
"嗯，用户想要一个天气查询助手...让我想想，根据规划规范，我需要定义文件清单，应该包含config.py、components.py这些基础文件。核心功能就是根据用户说的城市去查天气，那我需要一个天气查询工具组件...用{agent_mode}模式的话，我需要定义组件、连接关系、数据流向，还要考虑工具调用的错误处理..."

开始思考："""

    def _build_delegation_prompt(
        self,
        todo: TodoItem,
        task_plan: TaskPlan,
        wisdom: Any,
        mode_plan: Optional[ModePlan],
        thinking_context: Optional[str] = None
    ) -> str:
        """构建委托提示词"""
        prompt_parts = []
        
        # 如果有思考过程，将其作为上下文添加到最前面
        if thinking_context:
            prompt_parts.extend([
                "## Agent 思考过程",
                thinking_context,
                "",
                "---",
                ""
            ])
        
        prompt_parts.extend([
            f"## 任务",
            f"{todo.description}",
            "",
            f"## 用户需求",
            f"{task_plan.user_input}",
            ""
        ])
        
        if mode_plan:
            prompt_parts.extend([
                "## 模式计划",
                f"模式: {mode_plan.mode.value}",
                f"文件清单: {mode_plan.files}",
                ""
            ])
        
        if wisdom and wisdom.get_relevant_context(todo.task_type):
            prompt_parts.extend([
                "## 历史经验",
                wisdom.get_relevant_context(todo.task_type),
                ""
            ])
        
        prompt_parts.append(f"## 要求\n{todo.expected_outcome}")
        
        return "\n".join(prompt_parts)
    
    def _get_skills_for_mode(self, agent_mode: AgentMode) -> List[str]:
        """根据模式获取技能列表"""
        skill_name = self.SKILL_NAME_MAP.get(agent_mode.value)
        return [skill_name] if skill_name else []
    
    def _get_expected_files(self, agent_mode: AgentMode) -> List[str]:
        """根据模式获取预期文件列表"""
        from app.modes.base import get_mode_generator
        generator = get_mode_generator(agent_mode.value)
        return generator.get_required_files() if generator else []
    
    def _save_generated_files(self, files: Dict[str, str], workflow_dir: str):
        """
        保存生成的文件到工作流目录
        
        Args:
            files: 文件字典 {文件名: 内容}
            workflow_dir: 工作流目录路径
        """
        if not files:
            logger.warning("⚠️ 没有文件需要保存")
            return
        
        try:
            workflow_path = Path(workflow_dir)
            workflow_path.mkdir(parents=True, exist_ok=True)
            
            saved_count = 0
            for filename, content in files.items():
                file_path = workflow_path / filename
                file_path.write_text(content, encoding="utf-8")
                logger.info(f"💾 保存文件: {file_path}")
                saved_count += 1
            
            logger.info(f"✅ 共保存 {saved_count} 个文件到 {workflow_dir}")
        except Exception as e:
            logger.error(f"❌ 保存文件失败: {e}", exc_info=True)
            raise