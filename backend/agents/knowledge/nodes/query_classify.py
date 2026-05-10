# -*- coding: utf-8 -*-
"""
Query Classify Node - 问题分类
判断问题是单文档查询还是多文档查询
"""

import logging
from datetime import datetime
import time
from dashscope import Generation

from ..state import KnowledgeAgentState
from app.core.config import settings
from app.core.prompts import KNOWLEDGE_QUERY_CLASSIFY_SYSTEM

logger = logging.getLogger(__name__)

# 扩展关键词列表
SINGLE_DOC_KEYWORDS = [
    "本文", "这篇", "该文件", "该文档", "这个文件", "这篇文章", "这份文档",
    "该报告", "这份报告", "这篇报告", "该说明", "这份说明",
]
MULTI_DOC_KEYWORDS = [
    "多个文件", "多个文档", "不同文档", "各个文档", "对比", "比较",
    "不一致", "口径", "差异", "哪份", "哪些文档", "各个文件", "不同文件",
    "不同报告", "对比一下", "比较一下", "不同", "差异", "对比分析",
]


def query_classify(state: KnowledgeAgentState) -> dict:
    start_time = datetime.now()

    try:
        query = state["rewritten_query"]
        _cfg = state.get("config")

        # 用户显式指定多文档，跳过 LLM 判断
        if _cfg and _cfg.force_multi_doc is True:
            logger.info("[QueryClassify] 用户强制多文档，跳过 LLM 分类")
            return {
                "query_type": "multi_doc",
                "processing_log": [{"stage": "query_classify", "duration_ms": 0, "query_type": "multi_doc", "reason": "force_multi_doc"}],
            }

        logger.info(f"[QueryClassify] 开始分类问题: {query}")

        # 1. 先尝试快速启发式
        has_single = any(kw in query for kw in SINGLE_DOC_KEYWORDS)
        has_multi = any(kw in query for kw in MULTI_DOC_KEYWORDS)
        
        if has_single and not has_multi:
            logger.info("[QueryClassify] 检测到单文档关键词，快速返回 single_doc")
            duration = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "query_type": "single_doc",
                "processing_log": [{
                    "stage": "query_classify",
                    "duration_ms": duration,
                    "query_type": "single_doc",
                    "reason": "heuristic_single_doc",
                }],
            }
        
        if has_multi:
            logger.info("[QueryClassify] 检测到多文档关键词，快速返回 multi_doc")
            duration = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "query_type": "multi_doc",
                "processing_log": [{
                    "stage": "query_classify",
                    "duration_ms": duration,
                    "query_type": "multi_doc",
                    "reason": "heuristic_multi_doc",
                }],
            }
        
        # 2. 没把握时才用 LLM，但加超时！
        logger.info("[QueryClassify] 无明确关键词，调用 LLM 进行智能判断（超时3秒）")
        
        messages = [
            {
                "role": "system",
                "content": KNOWLEDGE_QUERY_CLASSIFY_SYSTEM,
            },
            {"role": "user", "content": f"问题: {query}\n\n分类结果:"},
        ]
        
        # 带超时调用 LLM
        try:
            response = Generation.call(
                api_key=settings.dashscope_api_key,
                model=state["config"].model,
                messages=messages,
                result_format="message",
                timeout=3,  # 3秒超时
            )
            
            if response.status_code == 200:
                classification = response.output.choices[0].message.get("content", "").strip().lower()
                if "single" in classification:
                    query_type = "single_doc"
                elif "multi" in classification:
                    query_type = "multi_doc"
                else:
                    logger.warning(f"[QueryClassify] LLM 返回无法识别: '{classification}'，默认 single_doc")
                    query_type = "single_doc"
            else:
                logger.warning(f"[QueryClassify] DashScope 错误 {response.status_code}，默认 single_doc")
                query_type = "single_doc"
        except Exception as llm_err:
            logger.warning(f"[QueryClassify] LLM 调用失败/超时: {llm_err}，默认 single_doc")
            query_type = "single_doc"
        
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"[QueryClassify] 分类完成 ({duration:.0f}ms): {query_type}")
        
        return {
            "query_type": query_type,
            "processing_log": [{
                "stage": "query_classify",
                "duration_ms": duration,
                "query_type": query_type,
            }],
        }

    except Exception as e:
        logger.error(f"[QueryClassify] 分类失败: {e}", exc_info=True)
        return {
            "query_type": "single_doc",
            "all_warnings": [f"问题分类失败，默认单文档查询: {e}"],
        }
