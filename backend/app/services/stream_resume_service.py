# -*- coding: utf-8 -*-
"""
SSE 流式响应续传服务
实现网络中断后的断点续传功能
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class StreamResumeService:
    """流式响应续传服务"""
    
    def __init__(self):
        self._active_streams: Dict[str, Dict[str, Any]] = {}
    
    async def save_stream_progress(
        self,
        conv_id: str,
        content: str,
        status: str = "streaming",  # streaming / completed / failed
        token_count: int = 0,
        error: Optional[str] = None,
    ):
        """
        保存流式生成进度到数据库
        
        Args:
            conv_id: 会话 ID
            content: 已生成的内容
            status: 状态（streaming/completed/failed）
            token_count: 已生成的 token 数量
            error: 错误信息（如果失败）
        """
        try:
            from app.db.database import AsyncSessionLocal
            from app.models.models import Message
            from sqlalchemy import select, update
            
            async with AsyncSessionLocal() as session:
                # 查找当前会话的 AI 消息
                result = await session.execute(
                    select(Message)
                    .where(Message.conv_id == conv_id)
                    .where(Message.role == "assistant")
                    .order_by(Message.created_at.desc())
                    .limit(1)
                )
                
                latest_message = result.scalar_one_or_none()
                
                if latest_message:
                    # 更新现有消息
                    latest_message.content = content
                    latest_message.sources = {
                        "status": status,
                        "token_count": token_count,
                        "updated_at": datetime.utcnow().isoformat(),
                        "error": error,
                    }
                else:
                    # 创建新消息
                    new_message = Message(
                        conv_id=conv_id,
                        role="assistant",
                        content=content,
                        sources={
                            "status": status,
                            "token_count": token_count,
                            "updated_at": datetime.utcnow().isoformat(),
                            "error": error,
                        }
                    )
                    session.add(new_message)
                
                await session.commit()
                
                logger.info(
                    f"[StreamResume] 保存进度: conv_id={conv_id}, "
                    f"content_len={len(content)}, status={status}"
                )
        
        except Exception as e:
            logger.error(f"[StreamResume] 保存进度失败: {e}", exc_info=True)
    
    async def get_stream_progress(
        self,
        conv_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        获取流式生成进度
        
        Args:
            conv_id: 会话 ID
            
        Returns:
            进度信息（content, status, token_count）或 None
        """
        try:
            from app.db.database import AsyncSessionLocal
            from app.models.models import Message
            from sqlalchemy import select
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Message)
                    .where(Message.conv_id == conv_id)
                    .where(Message.role == "assistant")
                    .order_by(Message.created_at.desc())
                    .limit(1)
                )
                
                latest_message = result.scalar_one_or_none()
                
                if not latest_message:
                    return None
                
                sources = latest_message.sources or {}
                
                return {
                    "content": latest_message.content,
                    "status": sources.get("status", "unknown"),
                    "token_count": sources.get("token_count", 0),
                    "created_at": latest_message.created_at.isoformat() if latest_message.created_at else None,
                    "error": sources.get("error"),
                }
        
        except Exception as e:
            logger.error(f"[StreamResume] 获取进度失败: {e}", exc_info=True)
            return None
    
    async def mark_stream_completed(
        self,
        conv_id: str,
        content: str,
        token_count: int,
    ):
        """标记流式生成为完成"""
        await self.save_stream_progress(
            conv_id=conv_id,
            content=content,
            status="completed",
            token_count=token_count,
        )
    
    async def mark_stream_failed(
        self,
        conv_id: str,
        content: str,
        error: str,
    ):
        """标记流式生成为失败"""
        await self.save_stream_progress(
            conv_id=conv_id,
            content=content,
            status="failed",
            error=error,
        )


# 单例
_stream_resume_service = None


def get_stream_resume_service():
    global _stream_resume_service
    if _stream_resume_service is None:
        _stream_resume_service = StreamResumeService()
    return _stream_resume_service
