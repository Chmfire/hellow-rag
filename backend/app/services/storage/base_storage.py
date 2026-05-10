# -*- coding: utf-8 -*-
"""
存储服务抽象基类
支持多种存储后端：MinIO、本地文件存储、阿里云OSS
"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseStorageService(ABC):
    """存储服务抽象基类"""

    @abstractmethod
    def upload_bytes(self, object_key: str, file_content: bytes) -> str:
        """
        上传字节内容

        Args:
            object_key: 对象路径
            file_content: 文件二进制内容

        Returns:
            object_key
        """
        pass

    @abstractmethod
    def upload_file(self, category_name: str, file_name: str, file_content: bytes) -> str:
        """
        上传文件到指定类目

        Args:
            category_name: 类目名称
            file_name: 文件名
            file_content: 文件二进制内容

        Returns:
            object_key
        """
        pass

    @abstractmethod
    def get_object_bytes(self, object_key: str) -> bytes:
        """
        获取对象字节内容

        Args:
            object_key: 对象路径

        Returns:
            文件字节内容
        """
        pass

    @abstractmethod
    def delete_objects(self, object_keys: list) -> int:
        """
        批量删除对象

        Args:
            object_keys: 对象路径列表

        Returns:
            实际删除数量
        """
        pass

    @abstractmethod
    def get_presigned_url(self, object_key: str, expires: int = 3600) -> str:
        """
        生成临时访问URL

        Args:
            object_key: 对象路径
            expires: 有效期（秒）

        Returns:
            临时访问URL
        """
        pass

    @abstractmethod
    def get_presigned_url_by_category(
        self, category_name: str, file_name: str, expires: int = 3600
    ) -> str:
        """
        通过类目名和文件名生成临时URL

        Args:
            category_name: 类目名称
            file_name: 文件名
            expires: 有效期（秒）

        Returns:
            临时访问URL
        """
        pass
