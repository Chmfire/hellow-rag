# -*- coding: utf-8 -*-
"""
本地文件存储服务实现
直接存储在本地文件系统
"""
import logging
import os
import hashlib
import time
from typing import Optional
from pathlib import Path
from urllib.parse import quote

from app.core.config import settings
from app.services.storage.base_storage import BaseStorageService

logger = logging.getLogger(__name__)


class LocalStorageService(BaseStorageService):
    """本地文件存储服务"""

    def __init__(self):
        self.storage_root = Path(settings.local_storage_root)
        self.api_base_url = f"http://{settings.api_host}:{settings.api_port}"
        self._ensure_storage_dir()
        logger.info(f"本地存储服务初始化: root={self.storage_root}")

    def _ensure_storage_dir(self):
        """确保存储目录存在"""
        if not self.storage_root.exists():
            self.storage_root.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建存储目录: {self.storage_root}")

    def _get_local_path(self, object_key: str) -> Path:
        """获取对象的本地路径"""
        # 清理路径，防止目录遍历攻击
        safe_key = object_key.replace('../', '').replace('..\\', '')
        return self.storage_root / safe_key

    def upload_bytes(self, object_key: str, file_content: bytes) -> str:
        try:
            local_path = self._get_local_path(object_key)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(file_content)
            logger.info(f"本地存储上传成功: {object_key}, size={len(file_content)}")
            return object_key
        except Exception as e:
            logger.error(f"本地存储上传失败: {object_key}, error={e}")
            raise Exception(f"本地存储上传失败: {e}")

    def upload_file(self, category_name: str, file_name: str, file_content: bytes) -> str:
        object_key = f"{category_name}/{file_name}"
        return self.upload_bytes(object_key, file_content)

    def get_object_bytes(self, object_key: str) -> bytes:
        try:
            local_path = self._get_local_path(object_key)
            data = local_path.read_bytes()
            logger.info(f"本地存储下载成功: {object_key}, size={len(data)}")
            return data
        except Exception as e:
            logger.error(f"本地存储下载失败: {object_key}, error={e}")
            raise Exception(f"本地存储下载失败: {e}")

    def delete_objects(self, object_keys: list) -> int:
        if not object_keys:
            return 0
        deleted_count = 0
        for object_key in object_keys:
            try:
                local_path = self._get_local_path(object_key)
                if local_path.exists():
                    local_path.unlink()
                    deleted_count += 1
                # 尝试删除空目录
                parent_dir = local_path.parent
                while parent_dir != self.storage_root:
                    if not any(parent_dir.iterdir()):
                        parent_dir.rmdir()
                        parent_dir = parent_dir.parent
                    else:
                        break
            except Exception as e:
                logger.warning(f"删除文件失败: {object_key}, error={e}")
        logger.info(f"本地存储批量删除: 请求 {len(object_keys)} 个, 成功 {deleted_count} 个")
        return deleted_count

    def get_presigned_url(self, object_key: str, expires: int = 3600) -> str:
        """
        生成临时访问URL
        本地存储使用代理URL，通过FastAPI代理访问
        """
        try:
            # 使用带过期时间的签名URL格式
            timestamp = int(time.time())
            signature = self._generate_signature(object_key, timestamp, expires)
            encoded_key = quote(object_key, safe='')
            url = f"{self.api_base_url}/api/v1/storage/file/{encoded_key}?ts={timestamp}&expires={expires}&sig={signature}"
            logger.info(f"生成本地存储临时 URL: {object_key}")
            return url
        except Exception as e:
            logger.error(f"生成本地存储临时 URL 失败: {object_key}, error={e}")
            raise Exception(f"生成本地存储临时 URL 失败: {object_key}, error={e}")

    def get_presigned_url_by_category(
        self, category_name: str, file_name: str, expires: int = 3600
    ) -> str:
        object_key = f"{category_name}/{file_name}"
        return self.get_presigned_url(object_key, expires)

    def _generate_signature(self, object_key: str, timestamp: int, expires: int) -> str:
        """生成签名用于验证URL"""
        secret = "local_storage_secret_key"  # 实际使用时应该从配置读取
        data = f"{object_key}{timestamp}{expires}{secret}"
        return hashlib.md5(data.encode()).hexdigest()[:8]

    def verify_signature(self, object_key: str, timestamp: int, expires: int, signature: str) -> bool:
        """验证签名"""
        expected_sig = self._generate_signature(object_key, timestamp, expires)
        if expected_sig != signature:
            return False
        # 检查过期
        current_time = int(time.time())
        if current_time > timestamp + expires:
            return False
        return True
