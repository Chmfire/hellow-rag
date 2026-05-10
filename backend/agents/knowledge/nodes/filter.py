# -*- coding: utf-8 -*-
"""
Filter Node - 按相关性分数过滤切片（multi_doc 路径专用）
增加门控评分：综合 score、rerank_score、chunk_level 等因素
"""

from typing import Dict, Any
from datetime import datetime

from ..state import KnowledgeAgentState


def _score(chunk) -> float:
    """兼容 RetrievedChunk dataclass 和 dict 两种格式取分数"""
    if isinstance(chunk, dict):
        return chunk.get("score", 0.0) or 0.0
    return getattr(chunk, "score", 0.0) or 0.0


def _gating_score(chunk) -> float:
    """门控评分：综合 score、rerank_score、chunk_level 等因素"""
    if isinstance(chunk, dict):
        score = chunk.get("score", 0.0) or 0.0
        rerank_score = chunk.get("rerank_score", 0.0) or 0.0
        chunk_level = chunk.get("chunk_level", 3)
    else:
        score = getattr(chunk, "score", 0.0) or 0.0
        rerank_score = getattr(chunk, "rerank_score", 0.0) or 0.0
        chunk_level = getattr(chunk, "chunk_level", 3)
    
    # 基础分数：优先使用 rerank_score，否则使用 score
    base_score = rerank_score if rerank_score > 0 else score
    
    # 层级加权：层级越高（数字越小）权重越大
    level_weight = 1.0 + (4.0 - chunk_level) * 0.1  # L1: 1.3, L2: 1.2, L3: 1.1, L4: 1.0
    
    return base_score * level_weight


def filter_chunks(state: KnowledgeAgentState) -> Dict[str, Any]:
    """
    按相关性分数过滤切片（multi_doc 路径）

    single_doc 路径经 Milvus RRF 融合后直接进入 generate，不经过此节点。
    """
    merged_chunks = state["merged_chunks"]
    config = state["config"]

    print(f"\n[Filter] Filtering {len(merged_chunks)} chunks, threshold={config.vector_score_threshold}")

    try:
        min_score = config.vector_score_threshold
        # 按门控分数排序并过滤
        scored_chunks = [(c, _gating_score(c)) for c in merged_chunks]
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        filtered = [c for c, s in scored_chunks if s >= min_score]

        print(f"[Filter] Kept {len(filtered)}/{len(merged_chunks)} chunks (gating scoring applied)")

        metrics = state["metrics"]
        metrics.chunks_after_filter = len(filtered)

        return {
            "filtered_chunks": filtered,
            "metrics": metrics,
            "processing_log": [{
                "stage": "filter",
                "timestamp": datetime.now().isoformat(),
                "chunks_before": len(merged_chunks),
                "chunks_after": len(filtered),
                "threshold": min_score,
                "gating_scoring": True,
            }]
        }

    except Exception as e:
        print(f"[Filter] Error: {e}")
        return {"all_errors": [f"Filtering failed: {e}"]}
