"""
测试 Agent（TesterAgent）

负责测试生成的代码
"""
import time
from pathlib import Path
from typing import Dict, Any, Optional, AsyncIterator
from loguru import logger

from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.agent.config.base import AgentConfig

from app.agents.base import VibeBaseAgent
from app.context.context_manager import ContextManager
from app.models.agent_result import AgentResult
from app.sandbox.sandbox import Sandbox


class TesterAgent(VibeBaseAgent):
    """
    测试 Agent - 继承 openJiuwen.BaseAgent
    
    职责：测试生成的代码
    关键约束：
    - ❌ 禁止使用 delegate_task 工具
    - ✅ 可以使用其他所有工具（包括沙箱）
    """
    
    def __init__(
        self,
        agent_config: AgentConfig,
        context_manager: Optional[ContextManager] = None,
        sandbox: Optional[Sandbox] = None
    ):
        """
        初始化测试 Agent
        
        Args:
            agent_config: Agent 配置（必须包含 model）
            context_manager: 上下文管理器
            sandbox: 沙箱实例（可选）
        """
        super().__init__(agent_config, context_manager)
        self.sandbox = sandbox or Sandbox()
        logger.info("初始化 TesterAgent")
    
    async def invoke(self, inputs: Dict, runtime: Runtime = None) -> Dict:
        """
        实现 openJiuwen 的 invoke 接口
        
        Args:
            inputs: 输入数据 {workflow_dir, conversation_id, smoke_tests, agent_mode, mode_plan, _event_queue}
            runtime: Runtime 实例
        
        Returns:
            执行结果 {tests_passed, test_output, errors}
        """
        try:
            workflow_dir = inputs.get("workflow_dir", "")
            conversation_id = inputs.get("conversation_id", "default")
            smoke_tests = inputs.get("smoke_tests", [])
            agent_mode = inputs.get("agent_mode")  # 获取 agent_mode
            mode_plan = inputs.get("mode_plan")  # 获取 mode_plan（可能包含测试查询信息）
            event_queue = inputs.get("_event_queue")  # 获取事件队列
            
            # 在沙箱中执行测试
            test_result = await self._test_in_sandbox(
                workflow_dir, conversation_id, smoke_tests, agent_mode, mode_plan, event_queue
            )

            # 确定测试命令（用于展示）
            files = self._load_workflow_files(Path(workflow_dir))
            test_command = self._determine_test_command(smoke_tests, files, agent_mode, mode_plan)

            # 构建测试结果数据
            result_data = {
                "tests_passed": test_result["success"],
                "test_output": test_result["output"],
                "errors": test_result.get("error"),
                "execution_time": test_result.get("execution_time", 0.0),
                "command": test_command,  # 测试命令
                "smoke_tests": smoke_tests  # 测试用例列表
            }

            # 根据测试结果返回成功或失败
            if test_result["success"]:
                return AgentResult.success_result(data=result_data).to_dict()
            else:
                error_msg = test_result.get("error") or "测试未通过"
                return AgentResult.failure_result(error=error_msg, data=result_data).to_dict()
        
        except Exception as e:
            logger.error(f"测试失败: {e}", exc_info=True)
            return AgentResult.failure_result(error=str(e)).to_dict()
    
    async def stream(self, inputs: Dict, runtime: Runtime = None) -> AsyncIterator[Any]:
        """实现 openJiuwen 的 stream 接口"""
        result = await self.invoke(inputs, runtime)
        yield result
    
    def _create_error_result(self, error_msg: str) -> Dict[str, Any]:
        """创建错误结果字典"""
        return {
            "success": False,
            "output": "",
            "error": error_msg,
            "execution_time": 0.0
        }
    
    def _load_workflow_files(self, workflow_path: Path) -> Dict[str, str]:
        """加载工作流目录中的所有 Python 文件"""
        py_files = list(workflow_path.glob("*.py"))
        if not py_files:
            return {}
        
        files = {}
        for py_file in py_files:
            with open(py_file, "r", encoding="utf-8") as f:
                files[py_file.name] = f.read()
        return files
    
    def _determine_test_command(
        self, 
        smoke_tests: list, 
        files: Dict[str, str], 
        agent_mode: Optional[str] = None,
        mode_plan: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        确定测试命令
        
        Args:
            smoke_tests: 测试用例列表
            files: 文件字典
            agent_mode: Agent 模式（workflow/react/multi_agent）
            mode_plan: 模式计划（可能包含测试查询信息）
        
        Returns:
            测试命令字符串
        """
        # 优先使用 smoke_tests 中的测试命令（规划阶段已确定）
        if smoke_tests:
            test = smoke_tests[0]
            return test if test.startswith("python ") else f"python {test}"
        
        # 如果没有提供测试用例，按优先级查找入口文件
        entry_files = ["main.py", "workflow_builder.py", "local_agent.py", "leader_agent.py"]
        for entry_file in entry_files:
            if entry_file in files:
                return f"python {entry_file}"
        
        # 使用第一个可用文件
        first_file = list(files.keys())[0]
        logger.warning(f"⚠️ 未找到标准入口文件，尝试运行: python {first_file}")
        return f"python {first_file}"
    
    @staticmethod
    def _safe_encode_string(text: str) -> str:
        """安全编码字符串，确保可以输出到日志（处理 emoji 和特殊字符）"""
        import sys
        import locale
        
        try:
            # 获取系统编码
            system_encoding = locale.getpreferredencoding() or sys.stdout.encoding or 'utf-8'
            
            # 尝试用系统编码编码字符串，替换无法编码的字符
            try:
                # 先尝试编码为系统编码，如果成功说明可以用系统编码输出
                text.encode(system_encoding)
                return text
            except (UnicodeEncodeError, UnicodeError):
                # 如果系统编码无法编码，使用 UTF-8 的 replace 模式替换特殊字符
                # 然后尝试转换为系统编码可以接受的字符
                safe_text = text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                # 再次尝试编码为系统编码
                try:
                    safe_text.encode(system_encoding)
                    return safe_text
                except (UnicodeEncodeError, UnicodeError):
                    # 如果还是失败，替换所有无法编码的字符为 ?
                    return safe_text.encode(system_encoding, errors='replace').decode(system_encoding, errors='replace')
        except Exception:
            # 最后的回退：使用 UTF-8 替换模式
            return text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
    
    def _print_test_output(self, text: str, label: str, log_func=logger.info):
        """打印测试输出文本"""
        if not text:
            log_func(f"{label}: (无输出)")
            return
        
        try:
            output_text = text if isinstance(text, str) else str(text)
            # 确保输出文本可以被安全编码
            output_text = self._safe_encode_string(output_text)
            
            log_func("-" * 80)
            log_func(f"{label}:")
            log_func("-" * 80)
            
            for line in output_text.split('\n'):
                cleaned_line = line.rstrip()
                if cleaned_line:
                    # 在输出前再次确保安全编码
                    safe_line = self._safe_encode_string(cleaned_line)
                    try:
                        log_func(f"  {safe_line}")
                    except (UnicodeEncodeError, UnicodeDecodeError) as e:
                        # 如果仍然失败，使用 repr 输出
                        logger.warning(f"无法编码某行内容，使用安全表示: {type(e).__name__}")
                        log_func(f"  {repr(cleaned_line)}")
        except Exception as e:
            logger.warning(f"打印{label}时出错: {e}")
            try:
                log_func(f"  原始内容: {repr(text)}")
            except Exception:
                # 最后的回退：只输出类型信息
                log_func(f"  原始内容类型: {type(text).__name__}, 长度: {len(str(text))}")
    
    async def _test_in_sandbox(
        self,
        workflow_dir: str,
        conversation_id: str,
        smoke_tests: list,
        agent_mode: Optional[str] = None,
        mode_plan: Optional[Dict[str, Any]] = None,
        event_queue: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        在沙箱中执行测试
        
        Args:
            workflow_dir: 工作流目录
            conversation_id: 会话 ID
            smoke_tests: 最小可运行用例列表
            agent_mode: Agent 模式（workflow/react/multi_agent）
            mode_plan: 模式计划
            event_queue: 事件队列（用于发送进度事件）
        
        Returns:
            测试结果
        """
        import asyncio
        
        # 发送测试准备中的思考事件
        if event_queue:
            try:
                await event_queue.put({
                    "type": "step_thinking",
                    "step_id": "test",
                    "step_name": "测试阶段",
                    "message": "正在准备测试环境...",
                    "data": {"thought": "正在准备测试环境..."},
                    "timestamp": time.time()
                })
            except Exception as e:
                logger.warning(f"发送思考事件失败: {e}")
        workflow_path = Path(workflow_dir)
        if not workflow_path.exists():
            logger.warning(f"⚠️ 工作流目录不存在: {workflow_dir}")
            return self._create_error_result(f"工作流目录不存在: {workflow_dir}")
        
        files = self._load_workflow_files(workflow_path)
        if not files:
            logger.warning(f"⚠️ 工作流目录没有 Python 文件: {workflow_dir}")
            return self._create_error_result("工作流目录没有 Python 文件，可能代码生成步骤失败")
        
        logger.info(f"📁 找到 {len(files)} 个 Python 文件: {list(files.keys())}")
        
        # 发送文件加载完成的思考事件
        if event_queue:
            try:
                thought_msg = f"✓ 找到 {len(files)} 个文件: {', '.join(list(files.keys())[:3])}{'...' if len(files) > 3 else ''}\n正在设置沙箱环境..."
                await event_queue.put({
                    "type": "step_thinking",
                    "step_id": "test",
                    "step_name": "测试阶段",
                    "message": thought_msg,
                    "data": {"thought": thought_msg},
                    "timestamp": time.time()
                })
            except Exception as e:
                logger.warning(f"发送思考事件失败: {e}")
        
        # 创建或获取沙箱
        sandbox_path = self.sandbox.get_sandbox(conversation_id) or \
                      self.sandbox.create_sandbox(conversation_id, persistent=True)
        logger.info(f"📦 使用沙箱: {sandbox_path}")
        
        # 复制文件到沙箱并执行测试
        self.sandbox.copy_files(conversation_id, files)
        logger.info(f"📋 已复制 {len(files)} 个文件到沙箱")
        
        command = self._determine_test_command(smoke_tests, files, agent_mode, mode_plan)
        logger.info(f"🧪 执行测试命令: {command} (agent_mode={agent_mode})")
        
        # 发送开始执行测试的思考事件
        if event_queue:
            try:
                thought_msg = f"✓ 沙箱环境准备完成\n✓ 文件已复制到沙箱\n正在执行测试命令: {command}"
                await event_queue.put({
                    "type": "step_thinking",
                    "step_id": "test",
                    "step_name": "测试阶段",
                    "message": thought_msg,
                    "data": {"thought": thought_msg},
                    "timestamp": time.time()
                })
            except Exception as e:
                logger.warning(f"发送思考事件失败: {e}")
        
        result = self.sandbox.execute(conversation_id, command)
        
        # 打印测试结果
        self._print_test_results(result)
        
        # 发送测试结果的思考事件
        if event_queue:
            try:
                success = result.get('success', False)
                exec_time = result.get('execution_time', 0)
                if success:
                    thought_msg = f"✓ 测试执行完成\n✓ 测试通过 (耗时: {exec_time:.2f}秒)\n测试输出正常，代码运行符合预期"
                else:
                    error = result.get('error', '未知错误')
                    thought_msg = f"✗ 测试执行完成\n✗ 测试失败 (耗时: {exec_time:.2f}秒)\n错误信息: {error[:100]}{'...' if len(error) > 100 else ''}"
                
                await event_queue.put({
                    "type": "step_thinking",
                    "step_id": "test",
                    "step_name": "测试阶段",
                    "message": thought_msg,
                    "data": {"thought": thought_msg},
                    "timestamp": time.time()
                })
            except Exception as e:
                logger.warning(f"发送思考事件失败: {e}")
        
        return result
    
    def _print_test_results(self, result: Dict[str, Any]):
        """打印详细的测试结果"""
        execution_time = result.get('execution_time', 0)
        test_output = result.get('output', '')
        test_error = result.get('error')
        success = result.get('success', False)
        
        logger.info("=" * 80)
        logger.info("📊 测试执行结果")
        logger.info("=" * 80)
        logger.info(f"⏱️  执行时间: {execution_time:.2f} 秒")
        logger.info("✅ 测试状态: 通过" if success else "❌ 测试状态: 失败")
        
        self._print_test_output(test_output, "📤 测试输出 (stdout)", logger.info)
        
        if test_error:
            self._print_test_output(test_error, "⚠️  错误信息 (stderr)", logger.error)
        
        logger.info("=" * 80)
        
        if success:
            logger.info(f"✅ 测试通过 (总耗时: {execution_time:.2f}s)")
        else:
            error_msg = test_error or 'Unknown error'
            logger.warning(f"❌ 测试失败: {error_msg}")
