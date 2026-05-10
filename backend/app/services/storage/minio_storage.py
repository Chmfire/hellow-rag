# -*- coding: utf-8 -*-
"""
MinIO 存储服务实现
完全兼容 S3 API，使用 boto3 库
"""
import logging
import datetime
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.services.storage.base_storage import BaseStorageService

logger = logging.getLogger(__name__)


class MinIOStorageService(BaseStorageService):
    """MinIO 存储服务"""

    def __init__(self):
        self.endpoint_url = settings.minio_endpoint
        self.access_key = settings.minio_access_key
        self.secret_key = settings.minio_secret_key
        self.bucket = settings.minio_bucket
        self.region = settings.minio_region
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            use_ssl=False
        )
        
        self._ensure_bucket_exists()
        logger.info(f"MinIO 服务初始化: bucket={self.bucket}, endpoint={self.endpoint_url}")

    def _ensure_bucket_exists(self):
        """确保 bucket 存在"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
            logger.info(f"Bucket {self.bucket} 已存在")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.info(f"创建 bucket: {self.bucket}")
                # 对于 us-east-1，不指定 LocationConstraint
                if self.region == 'us-east-1':
                    self.s3_client.create_bucket(Bucket=self.bucket)
                else:
                    self.s3_client.create_bucket(
                        Bucket=self.bucket,
                        CreateBucketConfiguration={'LocationConstraint': self.region}
                    )
            else:
                logger.error(f"检查 bucket 失败: {e}")
                raise Exception(f"检查 bucket 失败: {e}")

    def upload_bytes(self, object_key: str, file_content: bytes) -> str:
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=file_content
            )
            logger.info(f"MinIO 上传成功: {object_key}")
            return object_key
        except Exception as e:
            logger.error(f"MinIO 上传失败: {object_key}, error={e}")
            raise Exception(f"MinIO 上传失败: {e}")

    def upload_file(self, category_name: str, file_name: str, file_content: bytes) -> str:
        object_key = f"{category_name}/{file_name}"
        return self.upload_bytes(object_key, file_content)

    def get_object_bytes(self, object_key: str) -> bytes:
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=object_key
            )
            data = response['Body'].read()
            logger.info(f"MinIO 下载成功: {object_key}, size={len(data)}")
            return data
        except Exception as e:
            logger.error(f"MinIO 下载失败: {object_key}, error={e}")
            raise Exception(f"MinIO 下载失败: {e}")

    def delete_objects(self, object_keys: list) -> int:
        if not object_keys:
            return 0
        try:
            objects = [{'Key': k} for k in object_keys]
            response = self.s3_client.delete_objects(
                Bucket=self.bucket,
                Delete={'Objects': objects, 'Quiet': True}
            )
            deleted_count = len(response.get('Deleted', []))
            failed = len(object_keys) - deleted_count
            logger.info(f"MinIO 批量删除: 请求 {len(object_keys)} 个, 成功 {deleted_count} 个, 失败 {failed} 个")
            return deleted_count
        except Exception as e:
            logger.error(f"MinIO 批量删除失败: {e}")
            return 0

    def get_presigned_url(self, object_key: str, expires: int = 3600) -> str:
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': object_key},
                ExpiresIn=expires
            )
            logger.info(f"生成临时 URL: {object_key}, expires={expires}s")
            return url
        except Exception as e:
            logger.error(f"生成临时 URL 失败: {object_key}, error={e}")
            raise Exception(f"生成临时 URL 失败: {object_key}, error={e}")

    def get_presigned_url_by_category(
        self, category_name: str, file_name: str, expires: int = 3600
    ) -> str:
        object_key = f"{category_name}/{file_name}"
        return self.get_presigned_url(object_key, expires)
