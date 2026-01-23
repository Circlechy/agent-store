"""
结果验证器（ResultVerifier）

负责验证 Agent 执行结果
"""
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from loguru import logger

from app.models.agent_result import AgentResult
from app.models.task import TodoItem, ModePlan


class VerificationReport:
    """验证报告"""
    
    def __init__(
        self,
        stage: str,
        passed: bool,
        failure_type: Optional[str] = None,
        diff: Optional[str] = None
    ):
        self.stage = stage  # plan/generate/test
        self.passed = passed
        self.failure_type = failure_type  # file_missing/code_error/requirement_mismatch/...
        self.diff = diff  # 缺失文件、诊断摘要、失败用例、下一步建议
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stage": self.stage,
            "passed": self.passed,
            "failure_type": self.failure_type,
            "diff": self.diff
        }


class ResultVerifier:
    """结果验证器"""
    
    def __init__(self, workflow_dir: str):
        """
        初始化验证器
        
        Args:
            workflow_dir: 工作流目录
        """
        self.workflow_dir = Path(workflow_dir)
    
    def verify_plan_result(
        self,
        result: AgentResult,
        expected_mode: str
    ) -> VerificationReport:
        """
        验证规划结果
        
        Args:
            result: Agent 执行结果
            expected_mode: 期望的模式
        
        Returns:
            验证报告
        """
        if not result.success:
            return VerificationReport(
                stage="plan",
                passed=False,
                failure_type="plan_failed",
                diff=f"规划失败: {result.error}"
            )
        
        mode_plan_data = result.data.get("mode_plan")
        if not mode_plan_data:
            return VerificationReport(
                stage="plan",
                passed=False,
                failure_type="plan_incomplete",
                diff="计划数据缺失"
            )
        
        # 验证计划完整性
        from app.models.task import ModePlan, AgentMode
        
        try:
            mode_plan = ModePlan(**mode_plan_data)
            
            # 验证必需字段
            if not mode_plan.files:
                return VerificationReport(
                    stage="plan",
                    passed=False,
                    failure_type="plan_incomplete",
                    diff="文件清单为空"
                )
            
            if mode_plan.mode != AgentMode(expected_mode):
                return VerificationReport(
                    stage="plan",
                    passed=False,
                    failure_type="plan_mismatch",
                    diff=f"模式不匹配: 期望 {expected_mode}, 实际 {mode_plan.mode.value}"
                )
            
            return VerificationReport(
                stage="plan",
                passed=True
            )
        
        except Exception as e:
            return VerificationReport(
                stage="plan",
                passed=False,
                failure_type="plan_invalid",
                diff=f"计划格式错误: {e}"
            )
    
    def verify_generation_result(
        self,
        result: AgentResult,
        mode_plan: ModePlan
    ) -> VerificationReport:
        """
        验证生成结果
        
        Args:
            result: Agent 执行结果
            mode_plan: 模式计划
        
        Returns:
            验证报告
        """
        if not result.success:
            return VerificationReport(
                stage="generate",
                passed=False,
                failure_type="generation_failed",
                diff=f"生成失败: {result.error}"
            )
        
        generated_files = result.data.get("files", {})
        
        # 1. 结构验收：必需文件是否齐全
        required_files = mode_plan.files
        
        # 文件名映射（向后兼容：将旧的文件名映射到新的文件名）
        # 例如：tools.py -> tools_analysis.py
        file_name_mapping = {
            "tools.py": "tools_analysis.py"
        }
        
        # 检查缺失的文件（考虑文件名映射）
        missing_files = []
        for file_name in required_files:
            # 检查原文件名是否存在
            if file_name in generated_files:
                logger.debug(f"✅ 文件存在: {file_name}")
                continue
            
            # 检查映射后的文件名是否存在
            mapped_name = file_name_mapping.get(file_name)
            if mapped_name and mapped_name in generated_files:
                # 映射后的文件存在，视为满足要求
                logger.info(f"✅ 文件映射匹配: {file_name} -> {mapped_name} (已生成)")
                continue
            
            # 文件不存在（原文件名和映射后的文件名都不存在）
            if mapped_name:
                logger.warning(f"⚠️ 文件缺失: {file_name} (期望映射到 {mapped_name}，但两者都不存在)")
            else:
                logger.warning(f"⚠️ 文件缺失: {file_name}")
            missing_files.append(file_name)
        
        if missing_files:
            return VerificationReport(
                stage="generate",
                passed=False,
                failure_type="file_missing",
                diff=f"缺失文件: {missing_files}"
            )
        
        # 2. 静态验收：代码无语法错误
        code_errors = []
        for filename, content in generated_files.items():
            if filename.endswith(".py"):
                error = self._check_python_syntax(content, filename)
                if error:
                    code_errors.append(f"{filename}: {error}")
        
        if code_errors:
            return VerificationReport(
                stage="generate",
                passed=False,
                failure_type="code_error",
                diff=f"代码错误: {'; '.join(code_errors)}"
            )
        
        return VerificationReport(
            stage="generate",
            passed=True
        )
    
    def verify_test_result(
        self,
        result: AgentResult
    ) -> VerificationReport:
        """
        验证测试结果
        
        Args:
            result: Agent 执行结果
        
        Returns:
            验证报告
        """
        if not result.success:
            return VerificationReport(
                stage="test",
                passed=False,
                failure_type="test_failed",
                diff=f"测试失败: {result.error}"
            )
        
        tests_passed = result.data.get("tests_passed", False)
        errors = result.data.get("errors")
        
        if not tests_passed:
            return VerificationReport(
                stage="test",
                passed=False,
                failure_type="test_failed",
                diff=f"测试未通过: {errors or '未知错误'}"
            )
        
        return VerificationReport(
            stage="test",
            passed=True
        )
    
    def _check_python_syntax(self, code: str, filename: str) -> Optional[str]:
        """
        检查 Python 代码语法
        
        Args:
            code: 代码内容
            filename: 文件名
        
        Returns:
            错误信息，如果无错误则返回 None
        """
        try:
            compile(code, filename, "exec")
            return None
        except SyntaxError as e:
            return f"语法错误: {e.msg} (行 {e.lineno})"
        except Exception as e:
            return f"编译错误: {e}"
