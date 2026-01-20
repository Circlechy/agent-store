from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, root_validator


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="搜索字符串")

    @root_validator(pre=True)
    def strip_query(cls, values):
        query = values.get("query", "")
        if isinstance(query, str):
            values["query"] = query.strip()
        return values


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ChunkResponse(BaseModel):
    """用于描述 SSE 事件中的 chunk 数据，和实际数据结构一致."""
    type: Optional[str]
    content: Optional[dict]
    timestamp: Optional[str]


class HealthStatus(BaseModel):
    version: str
    uptime_seconds: Optional[float]
    services: Optional[List[str]]
