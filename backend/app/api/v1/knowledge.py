# -*- coding: utf-8 -*-
"""Knowledge API Routes"""
import asyncio
from typing import Dict
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.models.requests import KnowledgeRequest
from app.models.responses import KnowledgeResponse
from app.services.knowledge_service import invoke_knowledge_qa, stream_knowledge_qa_sse
from app.services.stream_resume_service import get_stream_resume_service

router = APIRouter(prefix="/knowledge")

# 全局停止事件存储，key为session_id
_stop_events: Dict[str, asyncio.Event] = {}


@router.post("/", response_model=KnowledgeResponse, summary="Knowledge Base Q&A")
async def knowledge_qa(request: KnowledgeRequest):
    """RAG 问答，完整流水线：改写→分类→检索→过滤→重排→生成→质量检查"""
    model_name = request.model or settings.default_model

    # 多模态：用户图片 base64 → 上传 OSS → 生成预签名 URL
    query_image_url = None
    query_image_oss_key = None
    if request.query_image:
        try:
            import base64, uuid
            from app.services.oss_service import get_oss_service
            img_bytes = base64.b64decode(request.query_image)
            img_uuid = uuid.uuid4().hex[:12]
            # 路径：query_images/{user_id}/{kb_name}/{session_id}/{uuid}.jpg
            kb_name = request.collection or "default"
            oss_path = f"query_images/default/{kb_name}/{request.session_id}"
            query_image_oss_key = get_oss_service().upload_file(
                oss_path, f"{img_uuid}.jpg", img_bytes
            )
            query_image_url = get_oss_service().get_presigned_url(query_image_oss_key, expires=600)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"用户查询图片上传失败，降级为纯文字检索: {e}")

    result = await invoke_knowledge_qa(
        query=request.query,
        model_name=model_name,
        session_id=request.session_id,
        collection=request.collection or None,
        force_multi_doc=request.force_multi_doc,
        keyword_filter=request.keyword_filter or None,
        query_image_url=query_image_url,
        query_image_oss_key=query_image_oss_key,
    )
    return KnowledgeResponse(
        status_code=200,
        request_id=result["request_id"],
        session_id=result["session_id"],
        answer=result["answer"],
        confidence=result["confidence"],
        sources=result["sources"],
        model=result["model"],
        finish_reason="stop",
        thoughts=result["thoughts"],
        image_map=result["image_map"],
    )


@router.post("/stream", summary="Knowledge Base Q&A (SSE stream)")
async def knowledge_qa_stream(request: KnowledgeRequest):
    """RAG 问答流式输出：event meta / delta / done / error，生成阶段为 OpenAI 兼容 Chat Completions stream。"""
    model_name = request.model or settings.default_model

    # 创建或清除停止事件
    stop_event = asyncio.Event()
    _stop_events[request.session_id] = stop_event

    query_image_url = None
    query_image_oss_key = None
    if request.query_image:
        try:
            import base64
            import uuid as _uuid
            from app.services.oss_service import get_oss_service
            img_bytes = base64.b64decode(request.query_image)
            img_uuid = _uuid.uuid4().hex[:12]
            kb_name = request.collection or "default"
            oss_path = f"query_images/default/{kb_name}/{request.session_id}"
            query_image_oss_key = get_oss_service().upload_file(
                oss_path, f"{img_uuid}.jpg", img_bytes
            )
            query_image_url = get_oss_service().get_presigned_url(query_image_oss_key, expires=600)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning(f"用户查询图片上传失败，降级为纯文字检索: {e}")

    async def event_gen():
        full_answer = ""
        token_count = 0
        try:
            async for chunk in stream_knowledge_qa_sse(
                query=request.query,
                model_name=model_name,
                session_id=request.session_id,
                collection=request.collection or None,
                force_multi_doc=request.force_multi_doc,
                keyword_filter=request.keyword_filter or None,
                query_image_url=query_image_url,
                query_image_oss_key=query_image_oss_key,
                stop_event=stop_event,
            ):
                yield chunk
                
                # 跟踪生成的内容，用于断点续传
                if 'data: {"text":' in chunk:
                    import json
                    try:
                        data_str = chunk.split("data: ", 1)[1].strip()
                        data = json.loads(data_str)
                        full_answer += data.get("text", "")
                        token_count += 1
                        
                        # 每生成 10 个 token 保存一次进度
                        if token_count % 10 == 0:
                            await get_stream_resume_service().save_stream_progress(
                                conv_id=request.session_id,
                                content=full_answer,
                                status="streaming",
                                token_count=token_count,
                            )
                    except:
                        pass
                
                # 检查是否完成
                if 'event: done' in chunk:
                    await get_stream_resume_service().mark_stream_completed(
                        conv_id=request.session_id,
                        content=full_answer,
                        token_count=token_count,
                    )
        except Exception as e:
            # 异常时保存已生成的内容
            if full_answer:
                await get_stream_resume_service().mark_stream_failed(
                    conv_id=request.session_id,
                    content=full_answer,
                    error=str(e),
                )
        finally:
            # 清理停止事件
            if request.session_id in _stop_events:
                del _stop_events[request.session_id]

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/resume/{session_id}", summary="获取流式生成进度（用于断点续传）")
async def get_stream_resume(session_id: str):
    """
    获取指定会话的流式生成进度
    用于网络中断后恢复已生成的内容
    """
    resume_service = get_stream_resume_service()
    progress = await resume_service.get_stream_progress(session_id)
    
    if not progress:
        return {
            "status": "not_found",
            "message": "未找到该会话的生成进度",
            "can_resume": False
        }
    
    return {
        "status": "success",
        "session_id": session_id,
        "content": progress["content"],
        "token_count": progress["token_count"],
        "stream_status": progress["status"],  # streaming / completed / failed
        "can_resume": progress["status"] == "streaming",
        "error": progress.get("error"),
        "created_at": progress.get("created_at"),
    }


@router.post("/stop", summary="停止正在进行的问答")
async def stop_qa(session_id: str):
    """停止指定会话的正在进行的问答"""
    if session_id in _stop_events:
        _stop_events[session_id].set()
        return {"status": "success", "message": f"已发送停止信号到会话 {session_id}"}
    return {"status": "not_found", "message": f"未找到会话 {session_id} 的进行中任务"}
