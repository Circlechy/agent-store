"""
智慧管理器

管理跨任务的知识传递和积累
"""
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from loguru import logger

from app.config.settings import get_settings
from app.models.agent_result import AgentResult


class Wisdom:
    """智慧数据类"""
    
    def __init__(self):
        self.learnings: str = ""
        self.decisions: str = ""
        self.issues: str = ""
        self.verification: str = ""
        self.problems: str = ""
    
    @classmethod
    def empty(cls) -> "Wisdom":
        """创建空的智慧对象"""
        return cls()
    
    def get_relevant_context(self, task_type: str) -> str:
        """
        根据任务类型获取相关上下文
        
        Args:
            task_type: 任务类型（plan/generate/test/fix）
        
        Returns:
            相关上下文字符串
        """
        parts = []
        
        if self.learnings:
            parts.append(f"## 学习经验\n{self.learnings}")
        
        if self.decisions:
            parts.append(f"## 架构决策\n{self.decisions}")
        
        if task_type in ["test", "fix"] and self.issues:
            parts.append(f"## 已知问题\n{self.issues}")
        
        return "\n\n".join(parts) if parts else ""


class WisdomManager:
    """智慧管理器"""
    
    def __init__(self, wisdom_dir: Optional[Path] = None):
        """
        初始化智慧管理器
        
        Args:
            wisdom_dir: 智慧目录路径
        """
        settings = get_settings()
        if wisdom_dir is None:
            project_root = Path(__file__).parent.parent.parent.parent
            wisdom_dir = project_root / settings.wisdom_dir
        
        self.wisdom_dir = Path(wisdom_dir)
        self.wisdom_dir.mkdir(exist_ok=True)
    
    def read_wisdom(self, workflow_name: str) -> Wisdom:
        """
        读取智慧
        
        Args:
            workflow_name: 工作流名称
        
        Returns:
            Wisdom 对象
        """
        workflow_wisdom_dir = self.wisdom_dir / workflow_name
        
        if not workflow_wisdom_dir.exists():
            return Wisdom.empty()
        
        wisdom = Wisdom()
        
        # 读取各个文件
        wisdom.learnings = self._read_file(workflow_wisdom_dir / "learnings.md")
        wisdom.decisions = self._read_file(workflow_wisdom_dir / "decisions.md")
        wisdom.issues = self._read_file(workflow_wisdom_dir / "issues.md")
        wisdom.verification = self._read_file(workflow_wisdom_dir / "verification.md")
        wisdom.problems = self._read_file(workflow_wisdom_dir / "problems.md")
        
        return wisdom
    
    def update_wisdom(
        self,
        workflow_name: str,
        results: List[AgentResult]
    ):
        """
        更新智慧
        
        Args:
            workflow_name: 工作流名称
            results: Agent 执行结果列表
        """
        workflow_wisdom_dir = self.wisdom_dir / workflow_name
        workflow_wisdom_dir.mkdir(exist_ok=True)
        
        # 提取学习、决策、问题等
        learnings = self._extract_learnings(results)
        decisions = self._extract_decisions(results)
        issues = self._extract_issues(results)
        
        # 写入文件
        if learnings:
            self._write_file(workflow_wisdom_dir / "learnings.md", learnings)
        if decisions:
            self._write_file(workflow_wisdom_dir / "decisions.md", decisions)
        if issues:
            self._write_file(workflow_wisdom_dir / "issues.md", issues)
        
        logger.info(f"更新智慧: {workflow_name}")
    
    def _read_file(self, file_path: Path) -> str:
        """读取文件内容"""
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"读取文件失败: {file_path}, 错误: {e}")
        return ""
    
    def _write_file(self, file_path: Path, content: str):
        """写入文件"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"写入文件失败: {file_path}, 错误: {e}")
    
    def _extract_learnings(self, results: List[AgentResult]) -> str:
        """从结果中提取学习经验"""
        # 简单实现：提取成功模式
        learnings = []
        for result in results:
            if result.success and result.metadata.get("pattern"):
                learnings.append(f"- {result.metadata['pattern']}")
        
        return "\n".join(learnings) if learnings else ""
    
    def _extract_decisions(self, results: List[AgentResult]) -> str:
        """从结果中提取架构决策"""
        # 简单实现：提取决策信息
        decisions = []
        for result in results:
            if result.metadata.get("decision"):
                decisions.append(f"- {result.metadata['decision']}")
        
        return "\n".join(decisions) if decisions else ""
    
    def _extract_issues(self, results: List[AgentResult]) -> str:
        """从结果中提取问题"""
        # 提取错误和问题
        issues = []
        for result in results:
            if not result.success and result.error:
                issues.append(f"- {result.error}")
        
        return "\n".join(issues) if issues else ""
