# -*- coding: utf-8 -*-
"""
Top-K Select Node - 使用 Cross-Encoder 重排序并取 top-K（multi_doc 路径专用）
集成 Auto-merging 逻辑，自动合并相关的子分块到父级分块

single_doc 路径经 Milvus RRF 融合后直接进入 generate，不经过此节点。
"""

from typing import Dict, Any, List, Tuple
from collections import defaultdict
from datetime import datetime

from ..state import KnowledgeAgentState
from app.services.rerank_service import get_rerank_service
from app.services.parent_chunk_store import parent_chunk_store
from app.core.config import settings


def _score(chunk) -> float:
    """兼容 RetrievedChunk dataclass 和 dict 两种格式取分数"""
    if isinstance(chunk, dict):
        return chunk.get("rerank_score") or chunk.get("score", 0.0) or 0.0
    return getattr(chunk, "rerank_score", None) or getattr(chunk, "score", 0.0) or 0.0


def _merge_to_parent_level(docs: List[dict], threshold: int = 2) -> Tuple[List[dict], int]:
    """
    将同一父级下的子分块合并到父级分块
    返回 (合并后的文档列表, 合并的文档数量)
    """
    groups: Dict[str, List[dict]] = defaultdict(list)
    for doc in docs:
        parent_id = (doc.get("parent_chunk_id") or "").strip()
        if parent_id:
            groups[parent_id].append(doc)
    
    # 找出需要合并的父级分块
    merge_parent_ids = [
        parent_id for parent_id, children in groups.items() 
        if len(children) >= threshold
    ]
    
    if not merge_parent_ids:
        return docs, 0
    
    # 从 parent_chunk_store 获取父级分块
    parent_docs = parent_chunk_store.get_documents_by_ids(merge_parent_ids)
    parent_map = {item.get("chunk_id", ""): item for item in parent_docs if item.get("chunk_id")}
    
    merged_docs: List[dict] = []
    merged_count = 0
    
    for doc in docs:
        parent_id = (doc.get("parent_chunk_id") or "").strip()
        if not parent_id or parent_id not in parent_map:
            merged_docs.append(doc)
            continue
        
        # 使用父级分块替换子分块
        parent_doc = dict(parent_map[parent_id])
        # 继承最高分数
        current_parent_score = parent_doc.get("score", 0.0)
        child_score = doc.get("score", 0.0)
        parent_doc["score"] = max(float(current_parent_score), float(child_score))
        # 标记为合并的
        parent_doc["merged_from_children"] = True
        parent_doc["merged_child_count"] = len(groups[parent_id])
        merged_docs.append(parent_doc)
        merged_count += 1
    
    # 去重（避免同一个父级分块被多次添加）
    deduped: List[dict] = []
    seen = set()
    for item in merged_docs:
        key = item.get("chunk_id") or (item.get("file_name"), item.get("chunk_index"), item.get("content"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    
    return deduped, merged_count


def _auto_merge_documents(docs: List[dict], top_k: int) -> Tuple[List[dict], Dict[str, Any]]:
    """
    Auto-merging 逻辑：两段自动合并 L3→L2→L1
    返回 (合并后的文档列表, 合并元数据)
    """
    auto_merge_enabled = settings.auto_merge_enabled
    auto_merge_threshold = settings.auto_merge_threshold
    
    if not auto_merge_enabled or not docs:
        return docs[:top_k], {
            "auto_merge_enabled": auto_merge_enabled,
            "auto_merge_applied": False,
            "auto_merge_threshold": auto_merge_threshold,
            "auto_merge_replaced_chunks": 0,
            "auto_merge_steps": 0,
        }
    
    # 两段自动合并：L3→L2，再 L2→L1
    merged_docs, merged_count_l3_l2 = _merge_to_parent_level(docs, threshold=auto_merge_threshold)
    merged_docs, merged_count_l2_l1 = _merge_to_parent_level(merged_docs, threshold=auto_merge_threshold)
    
    # 按分数排序并取 top_k
    merged_docs.sort(key=lambda x: _score(x), reverse=True)
    merged_docs = merged_docs[:top_k]
    
    replaced_count = merged_count_l3_l2 + merged_count_l2_l1
    return merged_docs, {
        "auto_merge_enabled": auto_merge_enabled,
        "auto_merge_applied": replaced_count > 0,
        "auto_merge_threshold": auto_merge_threshold,
        "auto_merge_replaced_chunks": replaced_count,
        "auto_merge_steps": int(merged_count_l3_l2 > 0) + int(merged_count_l2_l1 > 0),
    }


def select_top_k_chunks(state: KnowledgeAgentState) -> Dict[str, Any]:
    """
    对 filtered_chunks 使用 Cross-Encoder 重排序，然后应用 Auto-merging，取 top llm_context_top_k
    结果写入 reranked_chunks 和 merged_chunks（供 generate_answer 读取）
    """
    filtered_chunks = state["filtered_chunks"]
    config = state["config"]
    top_k = config.llm_context_top_k
    query = state["rewritten_query"]

    print(f"\n[TopKSelect] Processing {len(filtered_chunks)} chunks, top_k={top_k}")

    try:
        # 使用 Cross-Encoder 重排序
        rerank_service = get_rerank_service()
        reranked_chunks, rerank_meta = rerank_service.rerank(query, filtered_chunks, top_k=top_k)
        
        # 应用 Auto-merging
        merged_chunks, merge_meta = _auto_merge_documents(reranked_chunks, top_k)
        
        print(f"[TopKSelect] Selected top {len(merged_chunks)} chunks after reranking and auto-merging")
        
        if merge_meta.get("auto_merge_applied"):
            print(f"[TopKSelect] Auto-merging applied: {merge_meta.get('auto_merge_replaced_chunks')} chunks replaced")

        metrics = state["metrics"]
        metrics.chunks_after_rerank = len(merged_chunks)
        
        # 合并元数据
        processing_log = {
            "stage": "select_top_k",
            "timestamp": datetime.now().isoformat(),
            "chunks_in": len(filtered_chunks),
            "chunks_out": len(merged_chunks),
            "rerank_applied": True,
            "rerank_enabled": rerank_meta.get("rerank_enabled"),
        }
        processing_log.update(merge_meta)

        return {
            "reranked_chunks": merged_chunks,
            "merged_chunks": merged_chunks,
            "metrics": metrics,
            "processing_log": [processing_log]
        }

    except Exception as e:
        print(f"[TopKSelect] Error: {e}")
        import traceback
        traceback.print_exc()
        # 失败时使用原始排序
        sorted_chunks = sorted(filtered_chunks, key=_score, reverse=True)
        top_chunks = sorted_chunks[:top_k]
        return {
            "reranked_chunks": top_chunks,
            "merged_chunks": top_chunks,
            "all_warnings": [f"Top-K selection with rerank failed, using original ranking: {e}"],
        }
