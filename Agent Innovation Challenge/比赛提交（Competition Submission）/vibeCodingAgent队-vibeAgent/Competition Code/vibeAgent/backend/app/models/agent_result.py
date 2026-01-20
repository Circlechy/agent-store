"""
Agent 执行结果数据模型
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """Agent 执行结果"""
    success: bool = Field(description="是否成功")
    data: Dict[str, Any] = Field(default_factory=dict, description="结果数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata
        }
    
    @classmethod
    def success_result(cls, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> "AgentResult":
        """创建成功结果"""
        return cls(
            success=True,
            data=data,
            metadata=metadata or {}
        )
    
    @classmethod
    def failure_result(cls, error: str, data: Optional[Dict[str, Any]] = None) -> "AgentResult":
        """创建失败结果"""
        return cls(
            success=False,
            data=data or {},
            error=error
        )
