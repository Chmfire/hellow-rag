# -*- coding: utf-8 -*-
"""
存储服务 API
主要用于本地存储的文件代理访问
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from urllib.parse import unquote
import logging

from app.core.config import settings
from app.services.storage import get_storage_service
from app.services.storage.local_storage import LocalStorageService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/file/{object_key:path}")
async def serve_file(
    object_key: str,
    ts: int = Query(..., description="时间戳"),
    expires: int = Query(..., description="过期时间（秒）"),
    sig: str = Query(..., description="签名")
):
    """
    提供本地存储文件的访问
    仅在 STORAGE_TYPE=local 时有效
    """
    if settings.storage_type.lower() != "local":
        raise HTTPException(status_code=404, detail="此端点仅在本地存储模式下可用")
    
    object_key = unquote(object_key)
    
    # 验证签名
    storage_service = get_storage_service()
    if not isinstance(storage_service, LocalStorageService):
        raise HTTPException(status_code=500, detail="存储服务类型错误")
    
    if not storage_service.verify_signature(object_key, ts, expires, sig):
        raise HTTPException(status_code=403, detail="无效或过期的签名")
    
    # 获取文件路径
    local_path = storage_service._get_local_path(object_key)
    if not local_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 返回文件
    return FileResponse(
        path=local_path,
        filename=local_path.name,
        media_type="application/octet-stream"
    )
