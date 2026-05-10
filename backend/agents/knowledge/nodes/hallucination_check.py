# -*- coding: utf-8 -*-
"""
Node: 幻觉检测和引用溯源
在生成答案后，进行幻觉检测并添加引用溯源
"""
import logging
from datetime import datetime
from typing import Dict, Any

from ..state import KnowledgeAgentState
from app.services.hallucination_detection_service import (
    get_hallucination_detection_service
)

logger = logging.getLogger(__name__)


def hallucination_check_and_citation(state: KnowledgeAgentState) -> Dict[str, Any]:
    """
    幻觉检测和引用溯源节点

    Args:
        state: 当前 agent 状态

    Returns:
        更新后的状态，包含幻觉检测结果和引用信息
    """
    start_time = datetime.now()

    try:
        # 获取原始答案和检索到的 chunks
        messages = state.get("messages", [])
        chunks = state.get("merged_chunks", [])

        if not messages:
            logger.warning("[HallucinationCheck] 没有消息，跳过幻觉检测")
            return {}

        # 获取最后一个 AI 消息
        last_ai_message = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai":
                last_ai_message = msg.content or ""
                break
            elif isinstance(msg, dict) and msg.get("role") == "assistant":
                last_ai_message = msg.get("content", "")
                break

        if not last_ai_message:
            logger.warning("[HallucinationCheck] 没有找到 AI 消息，跳过幻觉检测")
            return {}

        logger.info(f"[HallucinationCheck] 开始幻觉检测和引用溯源: {len(last_ai_message)} 字符, {len(chunks)} 个 chunks")

        # 调用幻觉检测服务
        hallucination_service = get_hallucination_detection_service()
        result = hallucination_service.add_citations_to_answer(last_ai_message, chunks)

        duration = (datetime.now() - start_time).total_seconds() * 1000

        # 记录日志
        hallucination_rate = result['hallucination_detection'].get('hallucination_rate', 0.0)
        citation_count = len(result['citations'])
        logger.info(
            f"[HallucinationCheck] 完成 ({duration:.0f}ms): "
            f"幻觉率={hallucination_rate:.2%}, "
            f"引用数={citation_count}"
        )

        # 更新状态
        return {
            "hallucination_result": result,
            "cited_answer": result['cited_answer'],
            "processing_log": [{
                "stage": "hallucination_check",
                "duration_ms": duration,
                "hallucination_rate": hallucination_rate,
                "citation_count": citation_count,
                "overall_confidence": result['hallucination_detection'].get('overall_confidence', 0.0),
            }],
        }

    except Exception as e:
        logger.error(f"[HallucinationCheck] 幻觉检测失败: {e}", exc_info=True)
        return {
            "all_warnings": [f"幻觉检测失败，跳过: {e}"],
        }
