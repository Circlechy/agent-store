"""NovaStar FastAPI 服务器.

提供RESTful API接口，对接前端应用。
"""

import json
import logging
import os
import time
import uuid
from threading import RLock
from pathlib import Path
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from novastar.workflow.novastar_workflow import NovaStarWorkflow, create_novastar_workflow
from novastar.utils.config import get_config, load_config
from novastar.core.history_store import chat_history_store
from novastar.core.llm_wrapper import create_llm_from_config
from novastar.utils.multimodal_utils import speech_to_text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="NovaStar API",
    description="启明星儿童AI伴学系统API",
    version="1.0.0",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务（用于前端）
static_dir = project_root
if (static_dir / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 全局工作流实例
_workflow: Optional[NovaStarWorkflow] = None
_asr_llm = None
_recent_requests: Dict[str, float] = {}
_recent_requests_lock = RLock()


def _is_duplicate_request(user_id: str, query: str, window_ms: int = 600) -> bool:
    """简单去重：短时间内相同 user_id + query 视为重复请求."""
    if not user_id or not query:
        return False
    key = f"{user_id}::{query.strip()}"
    now = time.time() * 1000
    with _recent_requests_lock:
        last_ts = _recent_requests.get(key)
        _recent_requests[key] = now
        if last_ts and (now - last_ts) < window_ms:
            return True
        # 清理过旧记录，避免无界增长
        if len(_recent_requests) > 2000:
            expired = [k for k, ts in _recent_requests.items() if now - ts > 5 * window_ms]
            for k in expired:
                _recent_requests.pop(k, None)
    return False


def get_llm_config() -> dict:
    """从配置文件和环境变量获取LLM配置."""
    config = get_config()
    api_key = config.get_env("openai_api_key")
    api_base = config.get_env("openai_api_base")
    model_type = config.get_env("llm_model_type") or "openai"
    model_name = config.get_env("llm_model_name") or "gpt-4o-mini"
    
    return {
        "model_type": model_type,
        "model_name": model_name,
        "api_key": api_key,
        "api_base": api_base,
        "timeout": 60,
        "image_model_name": config.get_env("image_model_name") or None,
        "tts_model_name": config.get_env("tts_model_name") or None,
        "asr_model_name": config.get_env("asr_model_name") or None,
    }


def get_agent_config() -> dict:
    """从配置文件获取Agent配置."""
    config = get_config()
    
    return {
        "commander": config.get_commander_config(),
        "mentor": config.get_mentor_config(),
        "artist": config.get_artist_config(),
    }


def get_workflow() -> NovaStarWorkflow:
    """获取或创建工作流实例."""
    global _workflow
    if _workflow is None:
        logger.info("初始化NovaStar工作流...")
        llm_config = get_llm_config()
        agent_config = get_agent_config()
        _workflow = create_novastar_workflow(
            llm_config=llm_config,
            agent_config=agent_config,
        )
        logger.info("NovaStar工作流初始化完成")
    return _workflow


def get_asr_llm():
    """获取或创建语音识别LLM实例."""
    global _asr_llm
    if _asr_llm is None:
        llm_config = get_llm_config()
        _asr_llm = create_llm_from_config(llm_config)
    return _asr_llm


# Pydantic模型
class ChatRequest(BaseModel):
    """聊天请求模型."""
    query: str
    user_id: str = "default_user"
    conversation_id: Optional[str] = None
    intent: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    input_type: Optional[str] = "text"


class HistoryClearRequest(BaseModel):
    user_id: str = "default_user"


class SpeechToTextRequest(BaseModel):
    audio_base64: str
    user_id: str = "default_user"
    language: Optional[str] = None


def _normalize_agents(result: Dict[str, Any]) -> List[str]:
    agents: List[str] = []
    handled_by = result.get("handled_by")
    if handled_by:
        agents.append(str(handled_by))
    if result.get("agents"):
        for agent in result.get("agents", []):
            if agent and agent not in agents:
                agents.append(str(agent))
    return agents


def _build_user_message(request: ChatRequest, conversation_id: str) -> Dict[str, Any]:
    return {
        "role": "user",
        "content": request.query,
        "source": request.input_type or "text",
        "conversation_id": conversation_id,
    }


def _build_assistant_message(result: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
    raw_content = result.get("content")
    if raw_content in (None, ""):
        raw_content = result.get("response") or ""
    content = _format_content_for_history(raw_content)
    message = {
        "role": "assistant",
        "content": content,
        "intent": result.get("intent"),
        "handled_by": result.get("handled_by"),
        "agents": _normalize_agents(result),
        "conversation_id": conversation_id,
    }
    return message


def _format_content_for_history(content: Any) -> str:
    """将结构化内容规范为适合聊天记录展示的文本."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("answer_content") or item.get("answer") or item.get("content")
                if text:
                    parts.append(str(text))
                    continue
            if item is not None:
                parts.append(str(item))
        return "\n".join([part for part in parts if part])
    if isinstance(content, dict):
        text = content.get("text") or content.get("answer_content") or content.get("answer")
        if text:
            return str(text)
        inner = content.get("content")
        if inner:
            return _format_content_for_history(inner)
        title = content.get("title")
        paragraphs = content.get("paragraphs")
        if title and isinstance(paragraphs, list):
            para_texts: List[str] = []
            for para in paragraphs:
                if isinstance(para, dict):
                    para_texts.append(str(para.get("text") or ""))
                elif para is not None:
                    para_texts.append(str(para))
            body = "\n\n".join([p for p in para_texts if p])
            if body:
                return f"{title}\n\n{body}".strip()
            return str(title)
        if isinstance(paragraphs, list):
            para_texts = []
            for para in paragraphs:
                if isinstance(para, dict):
                    para_texts.append(str(para.get("text") or ""))
                elif para is not None:
                    para_texts.append(str(para))
            body = "\n\n".join([p for p in para_texts if p])
            if body:
                return body
        if title:
            return str(title)
        try:
            return json.dumps(content, ensure_ascii=False)
        except Exception:
            return str(content)
    return str(content)


# API路由
@app.get("/")
async def root():
    """根路径."""
    return {"message": "NovaStar API Server", "version": "1.0.0"}


@app.get("/health")
async def health():
    """健康检查."""
    return {"status": "healthy"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """处理聊天请求（非流式）.
    
    Args:
        request: 聊天请求
        
    Returns:
        响应结果
    """
    try:
        logger.info(
            "收到聊天请求: user_id=%s conversation_id=%s intent=%s",
            request.user_id,
            request.conversation_id,
            request.intent,
        )
        if _is_duplicate_request(request.user_id, request.query):
            logger.warning(
                "检测到重复聊天请求，已忽略: user_id=%s query=%s",
                request.user_id,
                request.query,
            )
            return JSONResponse(content={
                "success": True,
                "data": {
                    "response": "",
                    "content": "",
                    "intent": request.intent,
                    "handled_by": "",
                    "agents": [],
                    "duplicate": True,
                },
            })
        workflow = get_workflow()
        
        conversation_id = request.conversation_id or str(uuid.uuid4())
        result = await workflow.process_message(
            query=request.query,
            user_id=request.user_id,
            conversation_id=conversation_id,
            intent=request.intent,
            context=request.context or {"age": 6},
        )

        result.setdefault("agents", _normalize_agents(result))
        chat_history_store.extend(request.user_id, [
            _build_user_message(request, conversation_id),
            _build_assistant_message(result, conversation_id),
        ])
        
        return JSONResponse(content={
            "success": True,
            "data": result,
        })
    except Exception as e:
        logger.error(f"处理聊天请求失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """处理聊天请求（流式响应）.
    
    Args:
        request: 聊天请求
        
    Returns:
        SSE流式响应
    """
    def _is_tracer_chunk(chunk: Any) -> bool:
        if isinstance(chunk, dict):
            content = chunk.get("content")
            if isinstance(content, str) and content.startswith("type='tracer_"):
                return True
            payload = chunk.get("payload")
            if isinstance(payload, dict) and payload.get("traceId"):
                return True
        return False

    async def generate():
        try:
            logger.info(
                "收到流式聊天请求: user_id=%s conversation_id=%s intent=%s",
                request.user_id,
                request.conversation_id,
                request.intent,
            )
            if _is_duplicate_request(request.user_id, request.query):
                logger.warning(
                    "检测到重复流式请求，已忽略: user_id=%s query=%s",
                    request.user_id,
                    request.query,
                )
                yield "data: [DONE]\n\n"
                return

            workflow = get_workflow()
            conversation_id = request.conversation_id or str(uuid.uuid4())
            has_payload = False
            assistant_result: Dict[str, Any] = {
                "response": "",
                "content": "",
                "intent": None,
                "handled_by": None,
                "agents": [],
            }

            chat_history_store.append(request.user_id, _build_user_message(request, conversation_id))
            
            async for chunk in workflow.run(
                query=request.query,
                user_id=request.user_id,
                conversation_id=conversation_id,
                intent=request.intent,
                context=request.context or {"age": 6},
            ):
                if _is_tracer_chunk(chunk):
                    continue
                if isinstance(chunk, dict) and (chunk.get("response") or chunk.get("content")):
                    has_payload = True
                    response_chunk = chunk.get("response")
                    if response_chunk:
                        assistant_result["response"] = (
                            (assistant_result.get("response") or "")
                            + str(response_chunk)
                        )
                    content_chunk = chunk.get("content")
                    if isinstance(content_chunk, str) and content_chunk:
                        assistant_result["content"] = (
                            (assistant_result.get("content") or "")
                            + content_chunk
                        )
                    elif content_chunk is not None:
                        assistant_result["content"] = content_chunk
                if isinstance(chunk, dict):
                    if chunk.get("intent"):
                        assistant_result["intent"] = chunk.get("intent")
                    if chunk.get("handled_by"):
                        assistant_result["handled_by"] = chunk.get("handled_by")
                    if chunk.get("content_type"):
                        assistant_result["content_type"] = chunk.get("content_type")
                    if chunk.get("metadata"):
                        assistant_result["metadata"] = chunk.get("metadata")
                    if chunk.get("agents"):
                        assistant_result["agents"] = chunk.get("agents")
                # 格式化SSE数据
                data = {
                    "conversation_id": conversation_id,
                    "chunk": chunk,
                }
                
                # 发送SSE格式数据
                yield f"data: {JSONResponse(content=data).body.decode()}\n\n"

            if not has_payload:
                result = await workflow.process_message(
                    query=request.query,
                    user_id=request.user_id,
                    conversation_id=conversation_id,
                    intent=request.intent,
                    context=request.context or {"age": 6},
                )
                result.setdefault("agents", _normalize_agents(result))
                assistant_result.update(result)
                yield f"data: {JSONResponse(content={'conversation_id': conversation_id, 'chunk': result}).body.decode()}\n\n"

            assistant_result.setdefault("agents", _normalize_agents(assistant_result))
            chat_history_store.append(request.user_id, _build_assistant_message(assistant_result, conversation_id))
            
            # 发送结束标记
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"流式响应错误: {e}", exc_info=True)
            error_data = {
                "error": str(e),
                "conversation_id": request.conversation_id or str(uuid.uuid4()),
            }
            yield f"data: {JSONResponse(content=error_data).body.decode()}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/voice/transcribe")
async def voice_transcribe(request: SpeechToTextRequest):
    """语音转文本."""
    if not request.audio_base64:
        raise HTTPException(status_code=400, detail="audio_base64 不能为空")
    try:
        llm = get_asr_llm()
        text = await speech_to_text(
            llm=llm,
            audio=request.audio_base64,
            language=request.language,
        )
        if isinstance(text, str) and text.startswith("[模拟转录文本]"):
            raise HTTPException(status_code=502, detail="语音识别服务不可用")
        return JSONResponse(content={
            "success": True,
            "data": {"text": text},
        })
    except Exception as e:
        logger.error(f"语音转文本失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/history")
async def chat_history(user_id: str = "default_user"):
    """获取聊天历史（内存存储）."""
    history = chat_history_store.get(user_id)
    return JSONResponse(content={
        "success": True,
        "data": history,
    })


@app.post("/api/chat/history/clear")
async def clear_chat_history(request: HistoryClearRequest):
    """清空聊天历史（内存存储）."""
    chat_history_store.clear(request.user_id)
    return JSONResponse(content={
        "success": True,
        "data": {"user_id": request.user_id},
    })


@app.on_event("startup")
async def startup_event():
    """应用启动事件."""
    logger.info("NovaStar API服务器启动中...")
    
    # 加载配置
    load_config()
    
    # 预初始化工作流
    try:
        get_workflow()
        logger.info("NovaStar API服务器启动完成")
    except Exception as e:
        logger.error(f"工作流初始化失败: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件."""
    logger.info("NovaStar API服务器关闭中...")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
