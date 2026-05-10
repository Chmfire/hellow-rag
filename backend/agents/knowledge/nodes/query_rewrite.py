# -*- coding: utf-8 -*-
"""
Query Rewrite Node - 增强改写用户提问，支持多轮对话指代消解和查询扩展
"""

import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional

from dashscope import Generation

from ..state import KnowledgeAgentState, QueryExpansionStrategy
from app.core.config import settings
from app.core.prompts import KNOWLEDGE_QUERY_REWRITE_SYSTEM, KNOWLEDGE_QUERY_REWRITE_WITH_HISTORY_SYSTEM
from app.services.query_expansion_service import get_query_expansion_service

logger = logging.getLogger(__name__)

# 带入历史的最大轮数从 RAGConfig.memory_turns 读取，此处无需常量


def _normalize_query(query: str) -> str:
    """
    规范化查询文本
    """
    # 去除多余空格
    query = re.sub(r'\s+', ' ', query)
    # 去除首尾空格
    query = query.strip()
    # 确保以标点符号结尾
    if query and query[-1] not in '。！？.!?':
        query += '？'
    return query


def _detect_query_type(query: str) -> str:
    """
    简化的查询类型检测
    优先使用关键词检测，确保与后续检索参数调整配合
    """
    query_lower = query.lower()
    
    # 代码查询：包含代码标记或编程关键词
    if '```' in query or '`' in query:
        return 'code'
    if any(keyword in query_lower for keyword in ['python', 'javascript', 'java', '代码', '函数', '方法', '编程']):
        return 'code'
    
    # 分析查询：包含分析类关键词
    if any(keyword in query for keyword in ['分析', '比较', '评价', '建议', '总结', '归纳', '解释']):
        return 'analytical'
    
    # 创意查询：包含创意类关键词
    if any(keyword in query for keyword in ['创意', '设计', '策划', '方案', '想法', '构思']):
        return 'creative'
    
    # 默认返回 general，让后续的 _analyze_query 根据长度等参数调整
    return 'general'


def query_rewrite(state: KnowledgeAgentState) -> dict:
    start_time = datetime.now()

    try:
        original_query = state["original_query"]
        conversation_messages = state.get("messages", [])
        memory_turns = state["config"].memory_turns  # 从 config 读取，默认 2
        query_expansion_strategy = state["config"].query_expansion_strategy

        # 1. 预处理查询
        normalized_query = _normalize_query(original_query)
        query_type = _detect_query_type(normalized_query)

        # messages[-1] 是当前 query（HumanMessage），历史是 [:-1]
        history = conversation_messages[:-1] if len(conversation_messages) > 1 else []

        # 取最近 N 轮（每轮 = 1 human + 1 ai），截取尾部
        recent_history = history[-(2 * memory_turns):]

        if recent_history:
            # 有历史：用指代消解版 prompt，把历史拼入 messages
            system_prompt = KNOWLEDGE_QUERY_REWRITE_WITH_HISTORY_SYSTEM
            messages = [{"role": "system", "content": system_prompt}]
            for msg in recent_history:
                if hasattr(msg, "type"):
                    if msg.type == "human":
                        messages.append({"role": "user", "content": msg.content})
                    elif msg.type == "ai":
                        messages.append({"role": "assistant", "content": msg.content or ""})
                elif isinstance(msg, dict):
                    messages.append(msg)
            messages.append({"role": "user", "content": f"当前问题：{normalized_query}\n\n改写后的问题："})
            logger.info(f"[QueryRewrite] 带 {len(recent_history)} 条历史改写: {original_query} (类型: {query_type})")
        else:
            # 无历史：用简单版 prompt
            system_prompt = KNOWLEDGE_QUERY_REWRITE_SYSTEM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"原始问题: {normalized_query}\n\n改写后的问题:"},
            ]
            logger.info(f"[QueryRewrite] 无历史改写: {original_query} (类型: {query_type})")

        # 2. 调用 LLM 进行改写
        response = Generation.call(
            api_key=settings.dashscope_api_key,
            model=settings.llm_clean_model,  # 改写用轻量模型，降低延迟和成本
            messages=messages,
            result_format="message",
            top_p=0.7,  # 增加多样性
            temperature=0.3,  # 保持准确性
        )

        if response.status_code == 200:
            rewritten_query = response.output.choices[0].message.get("content", "").strip()
        else:
            logger.warning(f"[QueryRewrite] DashScope error {response.status_code}, 使用原始query")
            rewritten_query = ""

        if not rewritten_query or len(rewritten_query) < 2:
            rewritten_query = normalized_query

        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"[QueryRewrite] 完成 ({duration:.0f}ms): {original_query} → {rewritten_query}")

        # 3. 执行查询扩展（如果配置了策略）
        query_expansion_result = None
        expanded_query = None
        expansion_duration = 0
        
        if query_expansion_strategy != QueryExpansionStrategy.NONE:
            expansion_start = datetime.now()
            try:
                query_expansion_service = get_query_expansion_service()
                query_expansion_result = query_expansion_service.expand_query(
                    query=rewritten_query,
                    strategy=query_expansion_strategy
                )
                expanded_query = query_expansion_result.get("expanded_query", rewritten_query)
                expansion_duration = (datetime.now() - expansion_start).total_seconds() * 1000
                logger.info(f"[QueryExpansion] 完成 ({expansion_duration:.0f}ms): 策略={query_expansion_strategy.value}")
            except Exception as e:
                logger.error(f"[QueryExpansion] 扩展失败: {e}", exc_info=True)
                query_expansion_result = None
                expanded_query = rewritten_query

        result = {
            "rewritten_query": rewritten_query,
            "query_type": query_type,
            "expanded_query": expanded_query,
            "query_expansion_result": query_expansion_result,
            "processing_log": [{
                "stage": "query_rewrite",
                "duration_ms": duration,
                "original": original_query,
                "normalized": normalized_query,
                "rewritten": rewritten_query,
                "history_turns": len(recent_history) // 2,
                "query_type": query_type,
            }],
        }
        
        # 添加查询扩展的处理日志
        if query_expansion_strategy != QueryExpansionStrategy.NONE:
            result["processing_log"].append({
                "stage": "query_expansion",
                "duration_ms": expansion_duration,
                "strategy": query_expansion_strategy.value,
                "success": query_expansion_result.get("success", False) if query_expansion_result else False,
            })
        
        return result

    except Exception as e:
        logger.error(f"[QueryRewrite] 改写失败: {e}", exc_info=True)
        # 即使失败也进行基础预处理
        normalized_query = _normalize_query(original_query)
        query_type = _detect_query_type(normalized_query)
        
        return {
            "query": original_query,
            "rewritten_query": normalized_query,
            "query_type": query_type,
            "expanded_query": normalized_query,
            "query_expansion_result": None,
            "all_warnings": [f"问题改写失败，使用预处理后的问题: {e}"],
        }
