# -*- coding: utf-8 -*-
"""
任务业务逻辑
run_job_pipeline：切分 → 写 chunk → embedding → 写 Milvus → done
"""
import asyncio
import logging
from typing import Optional

from app.core.exceptions import NotFoundError
from app.db import get_job_repository, get_chunk_repository, get_file_repository, get_chunk_image_repository

logger = logging.getLogger(__name__)


# ── 查询 ──────────────────────────────────────────────────────────────────────

def list_jobs(kb_name: str, limit: int = 200) -> dict:
    from app.db import get_kb_repository
    kb = get_kb_repository().get_by_name(kb_name)
    if not kb:
        return {"jobs": [], "total": 0}
    jobs = get_job_repository().list_by_kb(kb["id"], limit=limit)
    return {"jobs": jobs, "total": len(jobs)}


def get_job_detail(job_id: str) -> dict:
    job = get_job_repository().get(job_id)
    if not job:
        raise NotFoundError("任务不存在")
    return {"job": job}


# ── 流水线 ────────────────────────────────────────────────────────────────────

async def run_job_pipeline(
    job_id: str,
    file_id: str,
    kb_id: str,
    kb_name: str,
    file_name: str,
    oss_key: str,
    image_mode: bool,
    chunk_size: int,
    chunk_overlap: int,
    image_dpi: int,
    sync_graph: bool = False,
) -> None:
    """
    完整流水线：
    pending → chunking → chunked → embedding → done
    任何阶段失败 → error
    如果 sync_graph=True，向量化完成后同步到知识图谱
    """
    job_repo = get_job_repository()
    file_repo = get_file_repository()

    try:
        # ── Step 1: 切分 ──────────────────────────────────────────────────────
        job_repo.update_status(job_id, "chunking", stage="正在切分文档")
        file_repo.update_status(file_id, "processing")

        file_content = await asyncio.to_thread(_download_file, oss_key)

        if image_mode:
            chunks, image_records = await asyncio.to_thread(
                _parse_image_mode,
                file_content=file_content,
                job_id=job_id,
                kb_name=kb_name,
                file_name=file_name,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                image_dpi=image_dpi,
            )
        elif kb.get("kb_type") == "table_enhanced":
            # 表格增强模式：使用 Unstructured 提取表格 + 文本
            chunks = await asyncio.to_thread(
                _parse_table_enhanced_mode,
                file_content=file_content,
                job_id=job_id,
                file_name=file_name,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            image_records = []
        else:
            chunks = await asyncio.to_thread(
                _parse_text_mode,
                file_content=file_content,
                file_name=file_name,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            image_records = []

        # ── Step 2: 写 chunk 到 PG ────────────────────────────────────────────
        # 先清理旧切片的 OSS 图片（bulk_insert 内部会 DELETE 旧 chunk，CASCADE 删 PG 图片记录，但 OSS 需手动清）
        from app.services.chunk_service import _delete_job_images_from_oss
        await asyncio.to_thread(_delete_job_images_from_oss, job_id)

        # 注入 auto_inject 元数据字段（如 title = 文件名前缀）
        from app.db import get_kb_repository
        kb = get_kb_repository().get_by_id(kb_id)
        metadata_fields = kb.get("metadata_fields") or [] if kb else []
        inject_map = {}
        for mf in metadata_fields:
            if mf.get("auto_inject") == "filename_prefix":
                inject_map[mf["key"]] = file_name.rsplit(".", 1)[0]
        if inject_map:
            for chunk in chunks:
                meta = chunk.get("metadata") or {}
                meta.update(inject_map)
                chunk["metadata"] = meta
            logger.info(f"[pipeline] 注入元数据: {inject_map}")

        chunk_repo = get_chunk_repository()
        if image_mode:
            await asyncio.to_thread(chunk_repo.bulk_insert_with_ids, job_id, file_name, chunks)
        else:
            await asyncio.to_thread(chunk_repo.bulk_insert, job_id, file_name, chunks)

        if image_records:
            await asyncio.to_thread(get_chunk_image_repository().bulk_insert, image_records)

        chunk_count = len(chunks)
        job_repo.update_status(job_id, "chunked", stage="切分完成，可审查切片后手动向量化", chunk_count=chunk_count, progress=50)
        file_repo.update_status(file_id, "chunked")
        logger.info(f"[pipeline] job_id={job_id} 切分完成，共 {chunk_count} 个切片，等待手动向量化")

    except Exception as e:
        logger.error(f"[pipeline] job_id={job_id} 失败: {e}")
        job_repo.update_status(job_id, "error", stage="处理失败", error_msg=str(e))
        file_repo.update_status(file_id, "error", error_msg=str(e))


# ── 手动触发向量化（切片编辑后重新上传）─────────────────────────────────────

async def upsert_job_to_milvus(job_id: str) -> dict:
    """将已切分的 job 重新向量化写入 Milvus（用于切片编辑后手动触发）"""
    job_repo = get_job_repository()
    job = job_repo.get(job_id)
    if not job:
        raise NotFoundError("任务不存在")

    from app.db import get_kb_repository, get_file_repository
    file_record = get_file_repository().get_by_id(job["file_id"])
    kb = get_kb_repository().get_by_id(job["kb_id"])
    if not file_record or not kb:
        raise NotFoundError("文件或知识库不存在")

    chunk_repo = get_chunk_repository()
    pg_chunks = chunk_repo.get_by_job(job_id)
    if not pg_chunks:
        raise NotFoundError("该 job 暂无切片数据")

    milvus_chunks = [
        {
            "chunk_id":    c["chunk_id"],
            "job_id":      job_id,
            "file_name":   file_record["file_name"],
            "chunk_index": c["chunk_index"],
            "content":     c["current_content"],
            "metadata":    c.get("metadata") or {},
        }
        for c in pg_chunks if c.get("current_content")
    ]

    from app.services.milvus_service import get_milvus_service
    milvus_svc = get_milvus_service()
    milvus_svc.get_or_create_collection(
        kb["name"], dim=kb["vector_dim"],
        kb_type=kb.get("kb_type", "standard"),
        image_vector_dim=kb.get("retrieval_config", {}).get("image_vector_dim", 1024),
    )

    if kb.get("kb_type") == "multimodal":
        result = await asyncio.to_thread(
            _upsert_multimodal_chunks, kb, job_id, milvus_chunks
        )
    else:
        result = await asyncio.to_thread(
            milvus_svc.upsert_chunks, kb["name"], milvus_chunks,
            kb["vector_dim"], kb.get("embedding_model"), kb.get("metadata_fields") or []
        )
    job_repo.mark_vectorized(job_id)

    # 如果用户选择了"同步到知识图谱"，向量化完成后同步到 KT
    if file_record.get("sync_graph"):
        try:
            from app.services.kg_graph_sync_service import get_kg_graph_sync_service
            kg_sync = get_kg_graph_sync_service()
            # 构建 chunk 向量映射（从 milvus_chunks 中提取）
            chunk_vectors = {
                c["chunk_id"]: c.get("dense") or c.get("embedding", [])
                for c in milvus_chunks
            }
            await kg_sync.sync_chunks_to_graph(
                job_id=job_id,
                kb_name=kb["name"],
                file_name=file_record["file_name"],
                chunks=[
                    {
                        "chunk_id": c["chunk_id"],
                        "content": c["current_content"],
                        "chunk_index": c["chunk_index"],
                        "vector": chunk_vectors.get(c["chunk_id"], [])
                    }
                    for c in pg_chunks if c.get("current_content")
                ],
            )
            logger.info(f"[pipeline] 图谱同步完成 job_id={job_id}")
        except Exception as e:
            # 图谱同步失败不影响主流程（向量库已成功）
            logger.error(f"[pipeline] 图谱同步失败 job_id={job_id}: {e}")

    return result


# ── 内部：文件下载 ────────────────────────────────────────────────────────────

def _download_file(oss_key: str) -> bytes:
    from app.services.oss_service import get_oss_service
    return get_oss_service().get_object_bytes(oss_key)


# ── 内部：图文模式切分 ────────────────────────────────────────────────────────

def _parse_image_mode(
    file_content: bytes,
    job_id: str,
    kb_name: str,
    file_name: str,
    chunk_size: int,
    chunk_overlap: int,
    image_dpi: int,
):
    from app.services.doc_image_parser import parse_pdf, parse_word
    ext = file_name.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        return parse_pdf(
            file_content=file_content,
            job_id=job_id,
            collection=kb_name,
            file_name=file_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            image_dpi=image_dpi,
        )
    elif ext in ("docx", "doc"):
        return parse_word(
            file_content=file_content,
            job_id=job_id,
            collection=kb_name,
            file_name=file_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    else:
        raise ValueError(f"图文模式不支持格式: {ext}")


# ── 内部：标准模式切分 ────────────────────────────────────────────────────────

def _parse_text_mode(
    file_content: bytes,
    file_name: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list:
    """
    标准模式：提取文本 → chunk_splitter 切分
    支持 PDF / DOCX / TXT / MD
    """
    from app.services.chunk_splitter import split_text_with_metadata

    ext = file_name.lower().rsplit(".", 1)[-1]
    text = _extract_text(file_content, ext, file_name)
    return split_text_with_metadata(
        text=text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        base_metadata={"file_name": file_name, "source": ext},
    )


def _extract_text(file_content: bytes, ext: str, file_name: str) -> str:
    if ext == "pdf":
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_content, filetype="pdf")
        return _extract_pdf_text_with_tables(doc)
    elif ext in ("docx", "doc"):
        import io
        from docx import Document
        doc = Document(io.BytesIO(file_content))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    elif ext in ("txt", "md"):
        for enc in ("utf-8", "gbk", "utf-16"):
            try:
                return file_content.decode(enc)
            except UnicodeDecodeError:
                continue
        return file_content.decode("utf-8", errors="ignore")
    else:
        # 尝试 UTF-8 文本
        return file_content.decode("utf-8", errors="ignore")


def _parse_table_enhanced_mode(
    file_content: bytes,
    job_id: str,
    file_name: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list:
    """
    表格增强模式：使用 Unstructured / PyMuPDF 提取表格，
    将表格转换为结构化文本后与正文一起切分。
    """
    from app.services.table_parser import get_table_parser
    from app.services.chunk_splitter import split_text_with_metadata

    parser = get_table_parser()
    tables, text_chunks = parser.parse_file(
        file_content=file_content,
        file_name=file_name,
        extract_tables=True,
        include_element_text=True,
    )

    # 将表格转换为结构化文本（适合 LLM 理解）
    table_texts = []
    for table in tables:
        table_text = table.to_text(format="structured")
        table_texts.append({
            "content": table_text,
            "page_number": table.page_number,
            "element_type": "table",
            "metadata": {
                "table_id": table.table_id,
                "table_title": table.title,
                "column_count": table.column_count,
                "row_count": table.row_count,
                "page": table.page_number,
            },
        })
        logger.info(
            f"[TableEnhanced] 表格 {table.table_id}: {table.title or '无标题'}, "
            f"{table.column_count}列×{table.row_count}行, 页码={table.page_number}"
        )

    # 合并表格文本和普通文本，按页码排序
    all_chunks = table_texts + text_chunks
    all_chunks.sort(key=lambda c: c.get("page_number", 0))

    # 将每个 chunk 的内容进行切分
    result = []
    chunk_index = 0
    for chunk in all_chunks:
        content = chunk["content"]
        metadata = chunk.get("metadata", {})
        if content.strip():
            sub_chunks = split_text_with_metadata(
                text=content,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                base_metadata={**metadata, "file_name": file_name, "source": "table_enhanced"},
            )
            for sc in sub_chunks:
                sc["metadata"]["chunk_index"] = chunk_index
                result.append(sc)
                chunk_index += 1

    logger.info(
        f"[TableEnhanced] 解析完成: {len(tables)} 个表格, {len(text_chunks)} 个文本块, "
        f"最终 {len(result)} 个切片"
    )
    return result


def _extract_pdf_text_with_tables(doc) -> str:
    """
    提取PDF文本，智能处理表格内容。
    检测表格结构，保留行列关系。
    """
    all_text = []
    for page in doc:
        page_text = _extract_page_text_with_tables(page)
        all_text.append(page_text)
    return "\n\n".join(all_text)


def _extract_page_text_with_tables(page) -> str:
    """
    提取单页文本，检测并处理表格。
    """
    # 获取所有文本块
    blocks = page.get_text("dict")["blocks"]
    text_blocks = []
    for b in blocks:
        if b["type"] != 0:  # 0表示文本块
            continue
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                text = span["text"].strip()
                if text:
                    text_blocks.append({
                        "text": text,
                        "bbox": span["bbox"],  # (x0, y0, x1, y1)
                    })
    
    if not text_blocks:
        return ""
    
    # 按y坐标分组（行）
    rows = _group_by_rows(text_blocks)
    
    # 检测表格：分析文本块的排列规律
    # 表格特征：多行文本具有相似的列数和对齐方式
    tables = _detect_tables(text_blocks, rows)
    
    # 提取非表格文本和表格文本
    page_text = []
    used_blocks = set()
    
    # 处理表格
    for table in tables:
        table_text = _format_table(table, text_blocks)
        page_text.append(table_text)
        for row_idx, col_idx, block_idx in table["cells"]:
            used_blocks.add(block_idx)
    
    # 处理非表格文本
    for i, block in enumerate(text_blocks):
        if i not in used_blocks:
            page_text.append(block["text"])
    
    return "\n".join(page_text)


def _group_by_rows(text_blocks: list) -> list:
    """
    按y坐标将文本块分组为行。
    返回：[[0, 1, 2, ...], ...] 原始索引列表
    """
    if not text_blocks:
        return []
    
    # 创建 (原始索引, 文本块) 对，按y坐标排序
    indexed_blocks = list(enumerate(text_blocks))
    sorted_blocks = sorted(indexed_blocks, key=lambda x: x[1]["bbox"][1])
    
    rows = []
    current_row = []
    current_y = sorted_blocks[0][1]["bbox"][1]
    y_threshold = 10  # y坐标差值阈值
    
    for orig_idx, block in sorted_blocks:
        y = block["bbox"][1]
        if abs(y - current_y) <= y_threshold:
            current_row.append(orig_idx)
        else:
            if current_row:
                rows.append(sorted(current_row))  # 按原始索引排序
            current_row = [orig_idx]
            current_y = y
    
    if current_row:
        rows.append(sorted(current_row))
    
    return rows


def _detect_tables(text_blocks: list, rows: list) -> list:
    """
    检测文本块中的表格结构。
    返回检测到的表格列表。
    """
    if not rows or len(rows) < 2:
        logger.debug(f"[PDF表格检测] 行数不足({len(rows) if rows else 0})，跳过表格检测")
        return []
    
    tables = []
    
    # 统计每行的列数
    col_counts = [len(row) for row in rows if len(row) >= 2]
    
    if not col_counts:
        logger.debug(f"[PDF表格检测] 没有检测到多列文本块")
        return []
    
    # 检测是否有稳定的列数（表格特征）
    from collections import Counter
    count_counter = Counter(col_counts)
    most_common = count_counter.most_common(1)
    
    if not most_common:
        return []
    
    common_col_count, frequency = most_common[0]
    logger.debug(f"[PDF表格检测] 最常见列数={common_col_count}，出现频率={frequency}/{len(rows)}")
    
    # 如果最常见的列数出现频率足够高，且列数>=2，则认为是表格
    if frequency >= len(rows) * 0.5 and common_col_count >= 2:
        # 找到表格起始行
        table_start = None
        table_end = None
        
        for i, row in enumerate(rows):
            if len(row) == common_col_count:
                if table_start is None:
                    table_start = i
                table_end = i
            else:
                if table_start is not None:
                    # 表格结束
                    break
        
        if table_start is not None and table_end is not None:
            table_rows = rows[table_start:table_end + 1]
            if len(table_rows) >= 2:
                logger.info(f"[PDF表格检测] 检测到表格: {common_col_count}列 x {len(table_rows)}行")
                # 构建表格
                table = {
                    "rows": table_rows,
                    "columns": common_col_count,
                    "cells": [],
                    "start_row": table_start,
                    "end_row": table_end,
                }
                
                # 填充单元格
                for row_idx, row in enumerate(table_rows):
                    for col_idx, block_idx in enumerate(row):
                        table["cells"].append((row_idx, col_idx, block_idx))
                
                tables.append(table)
    
    return tables


def _format_table(table: dict, text_blocks: list) -> str:
    """
    格式化表格为文本表示，保留行列结构信息。
    """
    rows = table["rows"]
    columns = table["columns"]
    cells = table["cells"]
    
    if not rows or not cells:
        return ""
    
    # 构建表格文本表示
    table_lines = []
    table_lines.append("【表格开始】")
    
    # 按行构建
    for row_idx in range(len(rows)):
        row_cells = []
        for col_idx in range(columns):
            # 查找对应的单元格
            cell_text = ""
            for r, c, block_idx in cells:
                if r == row_idx and c == col_idx:
                    cell_text = text_blocks[block_idx]["text"]
                    break
            row_cells.append(cell_text)
        table_lines.append(" | ".join(row_cells))
    
    table_lines.append("【表格结束】")
    
    return "\n".join(table_lines)


# ── 多模态向量化 ──────────────────────────────────────────────────────────────

def _upsert_multimodal_chunks(kb: dict, job_id: str, milvus_chunks: list) -> dict:
    """
    多模态知识库向量化：
    - 文本向量：qwen3-vl-embedding embed_text（与图片在同一语义空间）
    - 图片向量：qwen3-vl-embedding embed_image（nullable，无图片切片设为 None）
    
    优化：向量化前剥离图片占位符（<<IMAGE:xxx>>），避免污染向量和 BM25。
    """
    import re
    from app.services.multimodal_embedding_service import get_multimodal_embedding_service
    from app.services.milvus_service import get_milvus_service
    from app.services.oss_service import get_oss_service
    from app.db import get_chunk_image_repository

    _IMAGE_PH_RE = re.compile(r'<<IMAGE:[0-9a-f]+>>')
    
    mm_svc = get_multimodal_embedding_service()
    milvus_svc = get_milvus_service()
    oss_svc = get_oss_service()
    img_repo = get_chunk_image_repository()
    # 多模态 kb 的 vector_dim 已在创建时与 image_vector_dim 强制对齐
    image_dim = kb.get("vector_dim", 1024)
    kb_name = kb["name"]

    # 批量查询所有切片的图片记录
    chunk_ids = [c["chunk_id"] for c in milvus_chunks]
    img_records = img_repo.get_by_chunk_ids(chunk_ids) if chunk_ids else []
    # chunk_id → 第一张图片的 oss_key
    chunk_img_map: dict = {}
    for r in img_records:
        cid = r["chunk_id"]
        if cid not in chunk_img_map:
            chunk_img_map[cid] = r["oss_key"]

    import asyncio
    
    async def _process_chunk(chunk):
        content = chunk["content"]
        if not content:
            return None

        # 剥离图片占位符（向量化和 BM25 不感知占位符）
        clean_content = _IMAGE_PH_RE.sub('', content).strip()

        # 文本向量（qwen3-vl-embedding，与图片同语义空间）
        try:
            text_vec = await asyncio.to_thread(mm_svc.embed_text, clean_content, dimension=image_dim)
        except Exception as e:
            logger.error(f"[MultimodalUpsert] 文本向量化失败 chunk_id={chunk['chunk_id']}: {e}")
            return None

        # 图片向量（有图片则生成，否则填零向量，IP 相似度下零向量得分为 0 不影响排名）
        image_vec = [0.0] * image_dim
        oss_key = chunk_img_map.get(chunk["chunk_id"])
        if oss_key:
            try:
                img_url = oss_svc.get_presigned_url(oss_key, expires=600)
                vec = await asyncio.to_thread(mm_svc.embed_image, img_url, dimension=image_dim)
                if vec:
                    image_vec = vec
            except Exception as e:
                logger.warning(f"[MultimodalUpsert] 图片向量化失败，填零向量: {e}")

        row = {
            "chunk_id":    chunk["chunk_id"],
            "job_id":      job_id,
            "file_name":   chunk.get("file_name", ""),
            "chunk_index": int(chunk.get("chunk_index", 0)),
            "content":     clean_content,  # Milvus 存 clean 版本（不含占位符），BM25 基于此
            "dense":       text_vec,
            "image_dense": image_vec,
        }
        for k, v in (chunk.get("metadata") or {}).items():
            if k not in row:
                row[k] = v
        return row
    
    # 批量并行处理切片，添加速率限制
    async def _process_batch(batch):
        tasks = [_process_chunk(chunk) for chunk in batch]
        return await asyncio.gather(*tasks)
    
    # 分批次处理，每批10个，避免API速率限制
    batch_size = 10
    all_results = []
    loop = asyncio.get_event_loop()
    
    for i in range(0, len(milvus_chunks), batch_size):
        batch = milvus_chunks[i:i+batch_size]
        logger.info(f"[MultimodalUpsert] 处理批次 {i//batch_size + 1}/{(len(milvus_chunks)+batch_size-1)//batch_size}")
        batch_results = loop.run_until_complete(_process_batch(batch))
        all_results.extend([r for r in batch_results if r is not None])
        # 每批处理后稍作休息，避免API速率限制
        if i + batch_size < len(milvus_chunks):
            import time
            time.sleep(1)
    
    data = all_results

    if not data:
        return {"upsert_count": 0}

    batch_size = 50  # 多模态向量化较慢，批次小一点
    total = 0
    for i in range(0, len(data), batch_size):
        batch = data[i: i + batch_size]
        res = milvus_svc.client.upsert(collection_name=kb_name, data=batch)
        total += res.get("upsert_count", len(batch))

    logger.info(f"[MultimodalUpsert] upsert {total} 条到 {kb_name}")
    return {"upsert_count": total}
