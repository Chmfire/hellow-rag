# -*- coding: utf-8 -*-
"""
存储服务模块
支持多种存储后端：MinIO、本地文件存储、阿里云OSS
"""
from typing import Optional
from app.core.config import settings
from app.services.storage.base_storage import BaseStorageService

_instance: Optional[BaseStorageService] = None


def get_storage_service() -> BaseStorageService:
    """
    获取存储服务实例
    根据配置自动选择存储后端
    """
    global _instance
    if _instance is None:
        storage_type = settings.storage_type.lower()
        
        if storage_type == 'minio':
            from app.services.storage.minio_storage import MinIOStorageService
            _instance = MinIOStorageService()
        elif storage_type == 'local':
            from app.services.storage.local_storage import LocalStorageService
            _instance = LocalStorageService()
        elif storage_type == 'oss':
            from app.services.storage.oss_storage import OSSStorageService
            _instance = OSSStorageService()
        else:
            raise ValueError(f"不支持的存储类型: {storage_type}")
    
    return _instance


# 保持向后兼容，get_oss_service 别名
def get_oss_service() -> BaseStorageService:
    """
    保持向后兼容的接口
    实际返回 get_storage_service()
    """
    return get_storage_service()
