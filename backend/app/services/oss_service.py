# -*- coding: utf-8 -*-
"""
向后兼容的 OSS 服务接口
实际使用 get_storage_service() 来获取存储服务
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_instance = None


def get_oss_service():
    """
    保持向后兼容的接口
    实际返回 get_storage_service()
    """
    global _instance
    if _instance is None:
        from app.services.storage import get_storage_service
        _instance = get_storage_service()
    return _instance
