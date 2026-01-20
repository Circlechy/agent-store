"""
AI Agent框架集成预留接口
为openjiuwen等AI Agent框架提供标准化的服务调用入口
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field

from ..models import (
    AgentAction,
    AgentRequest,
    AgentResponse,
    ResponseStatus,
    SearchRequest,
)
from ..services import (
    get_search_service,
    SearchService,
    get_storage_service,
    StorageService,
    get_vector_db_service,
    VectorDBService,
    get_embedding_service,
    EmbeddingService,
    get_agent_service,
    AgentService,
)

router = APIRouter(prefix="/agent", tags=["Agent Integration"])


class AgentInterface:
    """
    Agent接口类
    为AI Agent框架提供标准化的服务调用方法

    设计原则：
    1. 统一的输入输出格式，便于Agent理解和调用
    2. 清晰的动作语义，便于LLM进行决策
    3. 丰富的上下文信息，支持多轮对话
    4. 可扩展的动作类型，便于后续功能扩展
    """

    def __init__(
        self,
        search_service: SearchService,
        storage_service: StorageService,
        vector_db_service: VectorDBService,
        embedding_service: EmbeddingService
    ):
        self.search_service = search_service
        self.storage_service = storage_service
        self.vector_db_service = vector_db_service
        self.embedding_service = embedding_service

    def get_available_actions(self) -> List[Dict[str, Any]]:
        """
        获取可用的动作列表
        供Agent了解可以执行的操作
        """
        return [
            {
                "action": "search",
                "description": "搜索图片，支持文本描述、图片相似度、图文混合搜索",
                "parameters": {
                    "query_text": {"type": "string", "description": "文本查询", "required": False},
                    "query_image_id": {"type": "string", "description": "图片ID查询", "required": False},
                    "top_k": {"type": "integer", "description": "返回数量", "default": 10},
                    "filter_tags": {"type": "array", "description": "标签过滤", "required": False}
                },
                "examples": [
                    {"query_text": "日落时的海滩", "top_k": 5},
                    {"query_image_id": "img_abc123", "top_k": 10}
                ]
            },
            {
                "action": "upload",
                "description": "上传新图片到相册",
                "parameters": {
                    "image_url": {"type": "string", "description": "图片URL", "required": True},
                    "tags": {"type": "array", "description": "标签列表", "required": False},
                    "description": {"type": "string", "description": "图片描述", "required": False}
                }
            },
            {
                "action": "delete",
                "description": "删除指定图片",
                "parameters": {
                    "image_id": {"type": "string", "description": "图片ID", "required": True}
                }
            },
            {
                "action": "update",
                "description": "更新图片信息",
                "parameters": {
                    "image_id": {"type": "string", "description": "图片ID", "required": True},
                    "tags": {"type": "array", "description": "新标签", "required": False},
                    "description": {"type": "string", "description": "新描述", "required": False}
                }
            },
            {
                "action": "analyze",
                "description": "分析图片内容（预留）",
                "parameters": {
                    "image_id": {"type": "string", "description": "图片ID", "required": True}
                }
            }
        ]

    def execute_action(
        self,
        action: AgentAction,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行Agent动作

        Args:
            action: 动作类型
            parameters: 动作参数
            context: 上下文信息（如对话历史、用户偏好等）

        Returns:
            执行结果
        """
        if action == AgentAction.SEARCH:
            return self._execute_search(parameters)
        elif action == AgentAction.UPLOAD:
            return self._execute_upload(parameters)
        elif action == AgentAction.DELETE:
            return self._execute_delete(parameters)
        elif action == AgentAction.UPDATE:
            return self._execute_update(parameters)
        elif action == AgentAction.ANALYZE:
            return self._execute_analyze(parameters)
        else:
            raise ValueError(f"不支持的动作类型: {action}")

    def _execute_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行搜索动作"""
        if not self.search_service.is_initialized:
            raise RuntimeError("搜索服务未初始化")

        result = self.search_service.search(
            query_text=params.get("query_text"),
            query_image_id=params.get("query_image_id"),
            query_image_url=params.get("query_image_url"),
            top_k=params.get("top_k", 10),
            filter_tags=params.get("filter_tags")
        )

        return {
            "success": True,
            "action": "search",
            "result": result,
            "message": f"找到 {result['total']} 张相关图片"
        }

    def _execute_upload(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行上传动作（预留，需要实现URL下载）"""
        # 预留：从URL下载并保存图片
        return {
            "success": False,
            "action": "upload",
            "message": "URL上传功能暂未实现，请使用/storage/upload接口"
        }

    def _execute_delete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行删除动作"""
        image_id = params.get("image_id")
        if not image_id:
            raise ValueError("必须提供image_id")

        # 删除文件
        file_deleted = self.storage_service.delete_image(image_id)

        # 删除向量
        vector_deleted = False
        if self.vector_db_service.is_initialized:
            vector_deleted = self.vector_db_service.delete(image_id)

        return {
            "success": file_deleted,
            "action": "delete",
            "result": {
                "file_deleted": file_deleted,
                "vector_deleted": vector_deleted
            },
            "message": "图片已删除" if file_deleted else "图片不存在"
        }

    def _execute_update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行更新动作"""
        image_id = params.get("image_id")
        if not image_id:
            raise ValueError("必须提供image_id")

        update_data = {}
        if "tags" in params:
            update_data["tags"] = params["tags"]
        if "description" in params:
            update_data["description"] = params["description"]

        if not update_data:
            return {
                "success": False,
                "action": "update",
                "message": "未提供任何更新内容"
            }

        success = self.vector_db_service.update_metadata(image_id, update_data)

        return {
            "success": success,
            "action": "update",
            "message": "更新成功" if success else "更新失败"
        }

    def _execute_analyze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行分析动作（预留）"""
        # 预留：接入VLM进行图片内容分析
        return {
            "success": False,
            "action": "analyze",
            "message": "图片分析功能暂未实现，将在后续版本中支持"
        }

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态，供Agent了解当前系统能力"""
        return {
            "embedding_service": self.embedding_service.is_initialized if self.embedding_service else False,
            "search_service": self.search_service.is_initialized if self.search_service else False,
            "storage_service": self.storage_service.is_initialized if self.storage_service else False,
            "vector_db_service": self.vector_db_service.is_initialized if self.vector_db_service else False,
            "total_images": self.storage_service.get_storage_stats()["total_images"] if self.storage_service.is_initialized else 0,
            "total_vectors": self.vector_db_service.count() if self.vector_db_service.is_initialized else 0
        }


# 全局Agent接口实例
_agent_interface: Optional[AgentInterface] = None


def get_agent_interface() -> AgentInterface:
    """获取Agent接口实例"""
    global _agent_interface

    if _agent_interface is None:
        _agent_interface = AgentInterface(
            search_service=get_search_service(),
            storage_service=get_storage_service(),
            vector_db_service=get_vector_db_service(),
            embedding_service=get_embedding_service()
        )

    return _agent_interface


# ==================== API路由 ====================

@router.get(
    "/actions",
    summary="获取可用动作列表",
    description="返回Agent可以执行的所有动作及其参数说明"
)
async def get_available_actions():
    """获取Agent可用动作列表"""
    agent = get_agent_interface()

    return {
        "status": "success",
        "actions": agent.get_available_actions()
    }


@router.post(
    "/execute",
    response_model=AgentResponse,
    summary="执行Agent动作",
    description="""
    统一的Agent动作执行接口，支持：
    - search: 搜索图片
    - upload: 上传图片（预留）
    - delete: 删除图片
    - update: 更新图片信息
    - analyze: 分析图片内容（预留）
    """
)
async def execute_agent_action(request: AgentRequest):
    """执行Agent动作"""
    agent = get_agent_interface()

    result = agent.execute_action(
        action=request.action,
        parameters=request.parameters,
        context=request.context
    )

    # 生成后续建议
    suggestions = _generate_suggestions(request.action, result)

    return AgentResponse(
        status=ResponseStatus.SUCCESS if result.get(
            "success") else ResponseStatus.ERROR,
        message=result.get("message", ""),
        action=request.action,
        result=result.get("result"),
        suggestions=suggestions
    )


@router.get(
    "/status",
    summary="获取系统状态",
    description="返回当前系统各服务的状态信息"
)
async def get_system_status():
    """获取系统状态"""
    agent = get_agent_interface()

    return {
        "status": "success",
        "system": agent.get_system_status()
    }


@router.get(
    "/schema",
    summary="获取API Schema",
    description="返回Agent调用所需的完整API Schema定义（OpenAPI格式）"
)
async def get_api_schema():
    """
    获取API Schema
    供openjiuwen等框架生成工具调用
    """
    return {
        "status": "success",
        "schema": {
            "name": "smart_album_api",
            "description": "智慧相册后端API，支持语义化图片检索",
            "version": "1.0.0",
            "base_url": "/api/v1/agent",
            "endpoints": [
                {
                    "path": "/execute",
                    "method": "POST",
                    "description": "执行Agent动作",
                    "request_body": {
                        "action": "string (search|upload|delete|update|analyze)",
                        "parameters": "object",
                        "context": "object (optional)"
                    }
                },
                {
                    "path": "/actions",
                    "method": "GET",
                    "description": "获取可用动作列表"
                },
                {
                    "path": "/status",
                    "method": "GET",
                    "description": "获取系统状态"
                }
            ]
        }
    }


def _generate_suggestions(action: AgentAction, result: Dict[str, Any]) -> List[str]:
    """根据动作结果生成后续建议"""
    suggestions = []

    if action == AgentAction.SEARCH:
        if result.get("success"):
            total = result.get("result", {}).get("total", 0)
            if total == 0:
                suggestions.append("尝试使用不同的关键词搜索")
                suggestions.append("检查是否有相关标签可以过滤")
            elif total > 10:
                suggestions.append("可以添加更具体的描述来缩小搜索范围")
                suggestions.append("尝试使用标签过滤来精确结果")

    elif action == AgentAction.DELETE:
        if result.get("success"):
            suggestions.append("删除操作已完成，相关数据已清理")

    elif action == AgentAction.UPDATE:
        if result.get("success"):
            suggestions.append("更新成功，可以搜索验证更新效果")

    return suggestions


# ==================== 聊天接口 ====================

class ChatMessage(BaseModel):
    """聊天消息模型"""
    query: str = Field(..., description="用户输入的自然语言查询")
    session_id: Optional[str] = Field(None, description="会话ID，用于多轮对话")
    top_k: int = Field(10, description="返回结果数量", ge=1, le=50)
    score_threshold: Optional[float] = Field(
        None, description="相似度阈值", ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    """聊天响应模型"""
    session_id: str = Field(..., description="会话ID")
    answer: str = Field(..., description="自然语言回复")
    intent: str = Field(..., description="识别的用户意图")
    optimized_query: str = Field(..., description="优化后的查询")
    results: Optional[Dict[str, Any]] = Field(None, description="搜索结果")
    suggestions: List[str] = Field(default_factory=list, description="后续建议")
    timestamp: str = Field(..., description="响应时间戳")


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Agent聊天接口",
    description="""
    智能对话接口，支持：
    
    1. **自然语言理解**：理解用户意图
    2. **查询优化**：将口语化描述转为精确语义（预留LLM集成）
    3. **工具调用**：自动调用搜索、删除等后端服务
    4. **自然回复**：生成对话式响应
    5. **多轮对话**：通过session_id保持上下文
    
    **使用示例**：
    ```json
    {
      "query": "我昨天拍的小狗照片",
      "top_k": 5
    }
    ```
    
    **预留扩展**：
    - 接入小参数LLM做查询优化
    - Function Calling工具链
    - RAG增强生成
    """
)
async def agent_chat(
    message: ChatMessage,
    search_svc: SearchService = Depends(get_search_service),
    agent_svc: AgentService = Depends(get_agent_service)
):
    """
    Agent聊天主接口

    处理流程：
    1. 创建/获取会话
    2. 意图识别
    3. 查询优化（预留LLM）
    4. 执行工具调用
    5. 生成自然语言响应
    6. 返回结果+建议
    """
    from datetime import datetime

    # 初始化Agent服务
    if not agent_svc.is_initialized:
        agent_svc.initialize()

    # 创建或获取会话
    session_id = message.session_id
    if not session_id:
        session_id = agent_svc.create_session()

    agent_svc.ensure_session(session_id)

    # 1. 意图识别
    # 优先使用 ReAct Agent 进行智能对话和意图处理
    if agent_svc.is_initialized and agent_svc._agent:
        try:
            # ReAct Agent 会自动判断是否需要调用工具（如搜索）
            # 对于 "你好"、"你是谁" 等闲聊，它会直接回复而不调用工具
            agent_result = await agent_svc.chat(message.query, session_id)
            response = agent_result.get("answer", "")
            images = agent_result.get("images") or []
            
            return ChatResponse(
                session_id=session_id,
                answer=response,
                intent="auto", # 由Agent自动决策
                optimized_query=message.query,
                results={"total": len(images), "images": images} if images else None,
                suggestions=[],
                timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            # Agent 执行失败，回退到规则引擎
            import logging
            logging.getLogger(__name__).error(f"Agent execution failed, falling back to rule-based engine: {e}")

    # --- 以下为降级处理逻辑 (Rule-based) ---
    intent_result = agent_svc.detect_intent(message.query)
    intent = intent_result["intent"]

    # 2. 查询优化（当前简化版，预留LLM接入点）
    optimized_query = agent_svc.optimize_query(message.query, session_id)

    # 3. 执行工具调用（当前主要支持搜索）
    results = None

    if intent == "search":
        if not search_svc.is_initialized:
            raise HTTPException(status_code=503, detail="搜索服务未初始化")

        # 调用搜索服务
        search_results = search_svc.search_by_text(
            query_text=optimized_query,
            top_k=message.top_k,
            score_threshold=message.score_threshold
        )

        results = {
            "total": len(search_results),
            "images": search_results
        }
    
    elif intent == "chat":
        # 普通聊天，没有特定操作
        results = {}

    elif intent == "delete":
        results = {"message": "删除功能需要指定图片ID，请使用 /agent/execute 接口"}

    elif intent == "upload":
        results = {"message": "上传功能请使用 /storage/upload 接口"}

    elif intent == "analyze":
        results = {"message": "图片分析功能即将上线"}

    else:
        results = {"message": "抱歉，我还不太理解您的意思"}

    # 4. 生成自然语言回复
    answer = agent_svc.generate_response(intent, results, message.query)

    # 5. 生成后续建议
    suggestions = agent_svc.generate_suggestions(intent, results)

    # 6. 返回响应
    return ChatResponse(
        session_id=session_id,
        answer=answer,
        intent=intent,
        optimized_query=optimized_query,
        results=results,
        suggestions=suggestions,
        timestamp=datetime.now().isoformat()
    )


@router.post(
    "/session/create",
    summary="创建新会话",
    description="创建一个新的对话会话，用于多轮对话场景"
)
async def create_session(
    user_id: Optional[str] = Body(None, description="用户ID（可选）"),
    agent_svc: AgentService = Depends(get_agent_service)
):
    """创建新会话"""
    if not agent_svc.is_initialized:
        agent_svc.initialize()

    session_id = agent_svc.create_session(user_id)

    return {
        "status": "success",
        "session_id": session_id,
        "message": "会话创建成功"
    }


@router.get(
    "/session/{session_id}",
    summary="获取会话信息",
    description="查看指定会话的历史记录和上下文"
)
async def get_session_info(
    session_id: str,
    agent_svc: AgentService = Depends(get_agent_service)
):
    """获取会话信息"""
    session = agent_svc.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

    return {
        "status": "success",
        "session": {
            "session_id": session_id,
            "user_id": session.get("user_id"),
            "created_at": session.get("created_at").isoformat(),
            "history_count": len(session.get("history", [])),
            "context": session.get("context", {})
        }
    }
