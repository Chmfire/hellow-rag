# -*- coding: utf-8 -*-
"""
查询扩展服务
支持 Step-Back、HyDE、Complex 三种查询扩展策略
"""
import logging
from enum import Enum
from typing import Dict, Any, Optional

import dashscope
from dashscope import Generation

from app.core.config import settings
from app.core.prompts import (
    QUERY_EXPANSION_STEP_BACK_QUESTION_PROMPT,
    QUERY_EXPANSION_STEP_BACK_ANSWER_PROMPT,
    QUERY_EXPANSION_HYDE_PROMPT,
    QUERY_EXPANSION_COMPLEX_PROMPT
)

logger = logging.getLogger(__name__)


class QueryExpansionStrategy(str, Enum):
    """查询扩展策略类型"""
    NONE = "none"                # 不使用查询扩展
    STEP_BACK = "step_back"      # Step-Back 策略
    HYDE = "hyde"                # Hypothetical Document Embedding
    COMPLEX = "complex"          # 复杂查询分解策略


class QueryExpansionService:
    """查询扩展服务"""

    def __init__(self):
        self.model = settings.llm_clean_model
        self.temperature = 0.2
        self.top_p = 0.8

    def expand_query(
        self, 
        query: str, 
        strategy: QueryExpansionStrategy = QueryExpansionStrategy.STEP_BACK
    ) -> Dict[str, Any]:
        """
        执行查询扩展
        
        Args:
            query: 原始查询
            strategy: 扩展策略
            
        Returns:
            包含扩展结果的字典
        """
        if strategy == QueryExpansionStrategy.NONE:
            return {
                "strategy": strategy,
                "original_query": query,
                "expanded_query": query,
                "success": True
            }

        try:
            if strategy == QueryExpansionStrategy.STEP_BACK:
                return self._step_back_expansion(query)
            elif strategy == QueryExpansionStrategy.HYDE:
                return self._hyde_expansion(query)
            elif strategy == QueryExpansionStrategy.COMPLEX:
                return self._complex_expansion(query)
            else:
                logger.warning(f"未知的查询扩展策略: {strategy}，使用原始查询")
                return {
                    "strategy": strategy,
                    "original_query": query,
                    "expanded_query": query,
                    "success": True
                }
        except Exception as e:
            logger.error(f"查询扩展失败: {e}", exc_info=True)
            return {
                "strategy": strategy,
                "original_query": query,
                "expanded_query": query,
                "success": False,
                "error": str(e)
            }

    def _step_back_expansion(self, query: str) -> Dict[str, Any]:
        """
        Step-Back 查询扩展策略
        
        步骤：
        1. 将具体问题抽象成更高层次的退步问题
        2. 回答退步问题，提供背景知识
        3. 将原问题与退步问题和答案组合成扩展查询
        """
        logger.info(f"执行 Step-Back 查询扩展: {query}")

        # 1. 生成退步问题
        step_back_question = self._call_llm(
            system_prompt=QUERY_EXPANSION_STEP_BACK_QUESTION_PROMPT,
            user_prompt=f"用户问题：{query}\n\n退步问题："
        )

        if not step_back_question:
            return {
                "strategy": QueryExpansionStrategy.STEP_BACK,
                "original_query": query,
                "expanded_query": query,
                "success": True,
                "step_back_question": None,
                "step_back_answer": None
            }

        # 2. 回答退步问题
        step_back_answer = self._call_llm(
            system_prompt=QUERY_EXPANSION_STEP_BACK_ANSWER_PROMPT,
            user_prompt=f"退步问题：{step_back_question}\n\n答案："
        )

        # 3. 组合扩展查询
        expanded_parts = [query]
        if step_back_question:
            expanded_parts.append(f"背景问题：{step_back_question}")
        if step_back_answer:
            expanded_parts.append(f"背景知识：{step_back_answer}")
        
        expanded_query = "\n\n".join(expanded_parts)

        logger.info(f"Step-Back 扩展完成: {len(expanded_query)} 字符")

        return {
            "strategy": QueryExpansionStrategy.STEP_BACK,
            "original_query": query,
            "step_back_question": step_back_question,
            "step_back_answer": step_back_answer,
            "expanded_query": expanded_query,
            "success": True
        }

    def _hyde_expansion(self, query: str) -> Dict[str, Any]:
        """
        HyDE (Hypothetical Document Embedding) 查询扩展策略
        
        为原始查询生成一个假设的、理想的回答文档，
        然后用这个假设文档进行检索
        """
        logger.info(f"执行 HyDE 查询扩展: {query}")

        hypothetical_doc = self._call_llm(
            system_prompt=QUERY_EXPANSION_HYDE_PROMPT,
            user_prompt=f"用户问题：{query}\n\n假设文档："
        )

        if not hypothetical_doc:
            return {
                "strategy": QueryExpansionStrategy.HYDE,
                "original_query": query,
                "expanded_query": query,
                "hypothetical_document": None,
                "success": True
            }

        # 组合扩展查询：原始查询 + 假设文档
        expanded_query = f"用户问题：{query}\n\n参考文档：{hypothetical_doc}"

        logger.info(f"HyDE 扩展完成: {len(expanded_query)} 字符")

        return {
            "strategy": QueryExpansionStrategy.HYDE,
            "original_query": query,
            "hypothetical_document": hypothetical_doc,
            "expanded_query": expanded_query,
            "success": True
        }

    def _complex_expansion(self, query: str) -> Dict[str, Any]:
        """
        复杂查询分解策略
        
        将复杂问题分解成多个子问题，扩展查询覆盖所有相关方面
        """
        logger.info(f"执行 Complex 查询扩展: {query}")

        expansion_result = self._call_llm(
            system_prompt=QUERY_EXPANSION_COMPLEX_PROMPT,
            user_prompt=f"原始问题：{query}\n\n扩展查询："
        )

        if not expansion_result:
            return {
                "strategy": QueryExpansionStrategy.COMPLEX,
                "original_query": query,
                "expanded_query": query,
                "sub_queries": [],
                "success": True
            }

        # 尝试提取子问题
        sub_queries = self._extract_sub_queries(expansion_result)

        # 组合扩展查询
        if sub_queries:
            expanded_query = f"原始问题：{query}\n\n相关问题：\n"
            for i, sub_q in enumerate(sub_queries, 1):
                expanded_query += f"{i}. {sub_q}\n"
        else:
            expanded_query = f"原始问题：{query}\n\n{expansion_result}"

        logger.info(f"Complex 扩展完成: 分解为 {len(sub_queries)} 个子问题")

        return {
            "strategy": QueryExpansionStrategy.COMPLEX,
            "original_query": query,
            "sub_queries": sub_queries,
            "expanded_query": expanded_query,
            "success": True
        }

    def _call_llm(
        self, 
        system_prompt: str, 
        user_prompt: str
    ) -> Optional[str]:
        """调用 LLM 生成内容"""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = Generation.call(
                api_key=settings.dashscope_api_key,
                model=self.model,
                messages=messages,
                result_format="message",
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=1024
            )

            if response.status_code == 200:
                content = response.output.choices[0].message.get("content", "").strip()
                return content if content else None
            else:
                logger.warning(f"LLM 调用失败: {response.status_code} - {response.message}")
                return None
        except Exception as e:
            logger.error(f"LLM 调用异常: {e}", exc_info=True)
            return None

    def _extract_sub_queries(self, text: str) -> list:
        """从 LLM 输出中提取子问题列表"""
        sub_queries = []
        lines = text.split("\n")
        
        for line in lines:
            line = line.strip()
            # 匹配 "1. xxx"、"- xxx" 等格式的子问题
            if line and (
                line[0].isdigit() and "." in line[:5] or 
                line.startswith("- ") or 
                line.startswith("* ")
            ):
                # 提取子问题文本
                sub_q = line.split(".", 1)[1].strip() if "." in line[:5] else line[2:].strip()
                if sub_q:
                    sub_queries.append(sub_q)
        
        return sub_queries


_instance = None


def get_query_expansion_service() -> QueryExpansionService:
    """获取查询扩展服务单例"""
    global _instance
    if _instance is None:
        _instance = QueryExpansionService()
    return _instance

