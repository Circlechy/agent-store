from __future__ import annotations

import logging
import os
import uuid
import shutil
import pyautogui

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from backend.api.models.schemas import ErrorResponse, SearchRequest, InteractionRequest
from backend.api.utils.concurrency import can_start_search, finish_search, start_search
from backend.api.utils.sse import sse_done, sse_error, sse_message
from backend.config.settings import settings
from jiuwen_memory_deepsearch.core.workflow import DeepsearchAgent
from openjiuwen.core.runtime.interaction.interactive_input import InteractiveInput

logger = logging.getLogger("jiuwen_memory_deepsearch.backend.routes.search")

router = APIRouter(prefix="/search", tags=["search"])


def _create_conflict_exception() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail=ErrorResponse(
            error="SEARCH_IN_PROGRESS",
            message="当前有搜索任务正在执行，请稍后再试"
        ).dict()
    )


def _serialize_chunk(chunk, session_id: str):
    chunk_type = getattr(chunk, "type", None)
    if chunk_type is None and isinstance(chunk, dict):
        chunk_type = chunk.get("type")
    if chunk_type == "__interaction__":
        payload = getattr(chunk, "payload", None)
        if payload is None and isinstance(chunk, dict):
            payload = chunk.get("payload", {})
        node_id = getattr(payload, "id", None)
        if node_id is None and isinstance(payload, dict):
            node_id = payload.get("id")
        prompt = getattr(payload, "value", None)
        if prompt is None and isinstance(payload, dict):
            prompt = payload.get("value")
        index = getattr(chunk, "index", None)
        if index is None and isinstance(chunk, dict):
            index = chunk.get("index")
        return sse_message({
            "event": "interaction",
            "session_id": session_id,
            "prompt": prompt,
            "index": index
        })
    return sse_message(chunk)


@router.post("", response_class=StreamingResponse)
async def search_endpoint(payload: SearchRequest) -> StreamingResponse:
    if settings.enable_concurrent_limit and not can_start_search():
        raise _create_conflict_exception()

    async def event_stream():
        start_search()
        agent = DeepsearchAgent()
        session_id = payload.session_id or f"ds-{uuid.uuid4().hex[:8]}"
        try:
            yield sse_message({"event": "metadata", "session_id": session_id})
            async for chunk in agent.run({"query": payload.query, "is_image": False, "session_id": session_id}):
                yield _serialize_chunk(chunk, session_id)
            yield sse_done()
        except Exception as exc:  # pragma: no cover
            logger.exception("搜索执行失败：%s", exc)
            yield sse_error("SEARCH_ERROR", str(exc))
        finally:
            finish_search()

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@router.post("/image", response_class=StreamingResponse)
async def search_image_endpoint(file: UploadFile = File(...)) -> StreamingResponse:
    if settings.enable_concurrent_limit and not can_start_search():
        raise _create_conflict_exception()

    # 保存图片到项目根目录的 temp 目录
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{file_extension}"
    file_path = os.path.join(temp_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async def event_stream():
        start_search()
        agent = DeepsearchAgent()
        session_id = f"ds-{uuid.uuid4().hex[:8]}"
        try:
            # 发送图片 URL 元数据给前端
            yield sse_message({"event": "metadata", "image_url": f"/temp/{filename}", "session_id": session_id})
            async for chunk in agent.run({"image_path": file_path, "is_image": True, "session_id": session_id}):
                yield _serialize_chunk(chunk, session_id)
            yield sse_done()
        except Exception as exc:
            logger.exception("图片搜索执行失败：%s", exc)
            yield sse_error("SEARCH_ERROR", str(exc))
        finally:
            finish_search()

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@router.post("/screenshot", response_class=StreamingResponse)
async def search_screenshot_endpoint() -> StreamingResponse:
    if settings.enable_concurrent_limit and not can_start_search():
        raise _create_conflict_exception()

    # 服务端截屏，保存到根目录 temp
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    filename = f"screenshot_{uuid.uuid4().hex}.png"
    file_path = os.path.join(temp_dir, filename)
    
    try:
        # 区域截图(左上角x,y,宽度,高度) - 参考用户提供代码
        region_screenshot = pyautogui.screenshot(region=(70, 90, 920, 1750))
        region_screenshot.save(file_path)
        logger.info(f"截屏完成: {file_path}")
    except Exception as e:
        logger.error(f"截屏失败: {e}")
        raise HTTPException(status_code=500, detail=f"截屏失败: {str(e)}")

    async def event_stream():
        start_search()
        agent = DeepsearchAgent()
        session_id = f"ds-{uuid.uuid4().hex[:8]}"
        try:
            # 发送图片 URL 给前端
            yield sse_message({"event": "metadata", "image_url": f"/temp/{filename}", "session_id": session_id})
            async for chunk in agent.run({"image_path": file_path, "is_image": True, "session_id": session_id}):
                yield _serialize_chunk(chunk, session_id)
            yield sse_done()
        except Exception as exc:
            logger.exception("截屏搜索执行失败：%s", exc)
            yield sse_error("SEARCH_ERROR", str(exc))
        finally:
            finish_search()

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@router.post("/interaction", response_class=StreamingResponse)
async def search_interaction_endpoint(payload: InteractionRequest) -> StreamingResponse:
    if settings.enable_concurrent_limit and not can_start_search():
        raise _create_conflict_exception()

    async def event_stream():
        start_search()
        agent = DeepsearchAgent()
        session_id = payload.session_id
        try:
            yield sse_message({"event": "metadata", "session_id": session_id})
            # 单组件中断：使用固定组件ID写入 user_inputs
            user_input = InteractiveInput()
            user_input.update("feedback_search_way", payload.search_way)
            async for chunk in agent.run({"interactive_input": user_input, "session_id": session_id}):
                yield _serialize_chunk(chunk, session_id)
            yield sse_done()
        except Exception as exc:
            logger.exception("交互恢复执行失败：%s", exc)
            yield sse_error("SEARCH_ERROR", str(exc))
        finally:
            finish_search()

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
