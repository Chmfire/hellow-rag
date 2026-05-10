# -*- coding: utf-8 -*-
"""
Parent Chunk 数据访问层
"""
import logging
from datetime import datetime
from typing import List, Optional
from app.db.pg_client import execute_sql, execute_select, execute_returning

logger = logging.getLogger(__name__)


def upsert_parent_chunk(chunk: dict) -> Optional[dict]:
    """
    插入或更新父级 chunk
    """
    chunk_id = chunk.get("chunk_id", "")
    if not chunk_id:
        return None

    sql = """
        INSERT INTO parent_chunks (
            chunk_id, text, filename, file_type, file_path, page_number,
            parent_chunk_id, root_chunk_id, chunk_level, chunk_idx, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (chunk_id) DO UPDATE SET
            text = EXCLUDED.text,
            filename = EXCLUDED.filename,
            file_type = EXCLUDED.file_type,
            file_path = EXCLUDED.file_path,
            page_number = EXCLUDED.page_number,
            parent_chunk_id = EXCLUDED.parent_chunk_id,
            root_chunk_id = EXCLUDED.root_chunk_id,
            chunk_level = EXCLUDED.chunk_level,
            chunk_idx = EXCLUDED.chunk_idx,
            updated_at = EXCLUDED.updated_at
        RETURNING *;
    """
    
    params = (
        chunk_id,
        chunk.get("text", ""),
        chunk.get("filename", ""),
        chunk.get("file_type", ""),
        chunk.get("file_path", ""),
        int(chunk.get("page_number", 0) or 0),
        chunk.get("parent_chunk_id", ""),
        chunk.get("root_chunk_id", ""),
        int(chunk.get("chunk_level", 0) or 0),
        int(chunk.get("chunk_idx", 0) or 0),
        datetime.utcnow(),
    )
    
    try:
        result = execute_returning(sql, params)
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Failed to upsert parent chunk {chunk_id}: {e}")
        return None


def get_parent_chunk_by_id(chunk_id: str) -> Optional[dict]:
    """
    通过 ID 获取父级 chunk
    """
    sql = """
        SELECT * FROM parent_chunks WHERE chunk_id = %s;
    """
    try:
        result = execute_select(sql, (chunk_id,))
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Failed to get parent chunk {chunk_id}: {e}")
        return None


def get_parent_chunks_by_ids(chunk_ids: List[str]) -> List[dict]:
    """
    通过 ID 列表获取父级 chunks
    """
    if not chunk_ids:
        return []
    
    placeholders = ",".join(["%s"] * len(chunk_ids))
    sql = f"""
        SELECT * FROM parent_chunks WHERE chunk_id IN ({placeholders});
    """
    
    try:
        result = execute_select(sql, tuple(chunk_ids))
        # 保持原始顺序
        chunk_map = {chunk["chunk_id"]: chunk for chunk in result}
        return [chunk_map[chunk_id] for chunk_id in chunk_ids if chunk_id in chunk_map]
    except Exception as e:
        logger.error(f"Failed to get parent chunks by ids: {e}")
        return []


def delete_parent_chunks_by_filename(filename: str) -> int:
    """
    通过文件名删除父级 chunks，返回删除的数量
    """
    if not filename:
        return 0
    
    # 先获取要删除的 chunk_ids
    get_sql = """
        SELECT chunk_id FROM parent_chunks WHERE filename = %s;
    """
    delete_sql = """
        DELETE FROM parent_chunks WHERE filename = %s;
    """
    
    try:
        chunks = execute_select(get_sql, (filename,))
        if chunks:
            execute_sql(delete_sql, (filename,))
            return len(chunks)
        return 0
    except Exception as e:
        logger.error(f"Failed to delete parent chunks for {filename}: {e}")
        return 0
