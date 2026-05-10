# -*- coding: utf-8 -*-
"""
父级分块文档存储（用于 Auto-merging Retriever）
参考 SuperMew/parent_chunk_store.py 实现
基于 PostgreSQL + Redis 的父级分块存储
"""
from typing import List
from app.core.cache import cache
from app.db import parent_chunk_repository


class ParentChunkStore:
    """基于 PostgreSQL + Redis 的父级分块存储"""

    @staticmethod
    def _to_dict(chunk: dict) -> dict:
        return {
            "text": chunk.get("text", ""),
            "filename": chunk.get("filename", ""),
            "file_type": chunk.get("file_type", ""),
            "file_path": chunk.get("file_path", ""),
            "page_number": chunk.get("page_number", 0),
            "chunk_id": chunk.get("chunk_id", ""),
            "parent_chunk_id": chunk.get("parent_chunk_id", ""),
            "root_chunk_id": chunk.get("root_chunk_id", ""),
            "chunk_level": chunk.get("chunk_level", 0),
            "chunk_idx": chunk.get("chunk_idx", 0),
        }

    @staticmethod
    def _cache_key(chunk_id: str) -> str:
        return f"parent_chunk:{chunk_id}"

    def upsert_documents(self, docs: List[dict]) -> int:
        """写入/更新父级分块，返回写入条数"""
        if not docs:
            return 0

        upserted = 0
        for doc in docs:
            chunk_id = (doc.get("chunk_id") or "").strip()
            if not chunk_id:
                continue

            # 存储到 PostgreSQL
            record = parent_chunk_repository.upsert_parent_chunk(doc)
            if record:
                # 缓存到 Redis
                cache_payload = self._to_dict(record)
                cache.set_json(self._cache_key(chunk_id), cache_payload)
                upserted += 1

        return upserted

    def get_documents_by_ids(self, chunk_ids: List[str]) -> List[dict]:
        """通过 ID 列表获取父级分块文档"""
        if not chunk_ids:
            return []

        ordered_results = {}
        missing_ids = []

        # 先从缓存获取
        for chunk_id in chunk_ids:
            key = (chunk_id or "").strip()
            if not key:
                continue
            cached = cache.get_json(self._cache_key(key))
            if cached:
                ordered_results[key] = cached
            else:
                missing_ids.append(key)

        # 缓存未命中，从数据库获取
        if missing_ids:
            db_chunks = parent_chunk_repository.get_parent_chunks_by_ids(missing_ids)
            for chunk in db_chunks:
                payload = self._to_dict(chunk)
                ordered_results[chunk["chunk_id"]] = payload
                cache.set_json(self._cache_key(chunk["chunk_id"]), payload)

        # 保持原始顺序
        return [ordered_results[chunk_id] for chunk_id in chunk_ids if chunk_id in ordered_results]

    def delete_by_filename(self, filename: str) -> int:
        """按文件名删除父级分块，返回删除条数"""
        if not filename:
            return 0

        # 从数据库删除
        deleted = parent_chunk_repository.delete_parent_chunks_by_filename(filename)
        if deleted > 0:
            # 删除缓存（删除模式匹配）
            cache.delete_pattern(f"parent_chunk:*")
        return deleted


parent_chunk_store = ParentChunkStore()
