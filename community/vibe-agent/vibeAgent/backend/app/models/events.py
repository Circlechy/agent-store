"""
SSE 事件数据模型
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class EventType(str, Enum):
    """事件类型"""
    # 规划阶段
    PLAN_STARTED = "plan_started"
    PLAN_COMPLETED = "plan_completed"
    PLAN_VERIFICATION_FAILED = "plan_verification_failed"
    PLAN_FAILED = "plan_failed"
    
    # 步骤阶段
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_THINKING = "step_thinking"
    STEP_ACTING = "step_acting"
    STEP_OBSERVING = "step_observing"
    
    # 生成阶段
    GENERATION_STARTED = "generation_started"
    GENERATION_COMPLETED = "generation_completed"
    GENERATION_VERIFICATION_FAILED = "generation_verification_failed"
    
    # 测试阶段
    TEST_STARTED = "test_started"
    TEST_COMPLETED = "test_completed"
    TEST_FAILED = "test_failed"
    
    # 迭代阶段
    ITERATION_STARTED = "iteration_started"
    ITERATION_COMPLETED = "iteration_completed"
    
    # 修复阶段
    FIX_STARTED = "fix_started"
    FIX_COMPLETED = "fix_completed"
    
    # 完成
    BUILD_COMPLETED = "build_completed"
    BUILD_FAILED = "build_failed"
    
    # 错误
    ERROR = "error"


class SSEEvent(BaseModel):
    """SSE 事件"""
    type: EventType = Field(description="事件类型")
    message: str = Field(default="", description="事件消息")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件数据")
    timestamp: Optional[float] = Field(default=None, description="时间戳（Unix 时间戳）")
    step_id: Optional[str] = Field(default=None, description="步骤ID（如果适用）")
    step_name: Optional[str] = Field(default=None, description="步骤名称（如果适用）")
    
    def to_sse_format(self) -> str:
        """转换为 SSE 格式"""
        import json
        import time
        
        if self.timestamp is None:
            self.timestamp = time.time()
        
        event_data = {
            "type": self.type.value,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp
        }
        
        # 添加可选字段（如果存在）
        if self.step_id is not None:
            event_data["step_id"] = self.step_id
        if self.step_name is not None:
            event_data["step_name"] = self.step_name
        
        return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
