# -*- coding: utf-8 -*-
"""
Rerank 服务
使用远程 API 对检索结果进行语义级重新排序，支持降级为原始排序
"""
import logging
import json
from typing import List, Dict, Any, Tuple

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


class RerankService:
    """
    Rerank 服务，支持远程 API 方式，失败时自动降级
    """

    def __init__(self):
        self.rerank_enabled = bool(settings.rerank_model and settings.rerank_host and settings.rerank_api_key)
        self.rerank_model = settings.rerank_model
        self.rerank_api_key = settings.rerank_api_key
        self.rerank_timeout = settings.rerank_timeout
        self.rerank_endpoint = self._get_rerank_endpoint()

        if self.rerank_enabled:
            logger.info(f"Rerank 服务初始化完成，模型: {self.rerank_model}, 端点: {self.rerank_endpoint}")
        else:
            logger.info("Rerank 服务未配置，将使用原始排序")

    def _get_rerank_endpoint(self) -> str:
        """获取 Rerank API 端点"""
        if not settings.rerank_host:
            return ""
        host = settings.rerank_host.strip().rstrip("/")
        return host if host.endswith("/v1/rerank") else f"{host}/v1/rerank"

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        对检索结果进行重排序，失败时自动降级为原始排序

        Args:
            query: 查询文本
            documents: 文档列表，每个文档需包含 'text' 或 'content' 字段
            top_k: 返回的文档数量

        Returns:
            (reranked_docs, meta) - 重排序后的文档和元数据
        """
        docs_with_rank = [{**doc, "rrf_rank": i} for i, doc in enumerate(documents, 1)]
        meta = {
            "rerank_enabled": self.rerank_enabled,
            "rerank_applied": False,
            "rerank_model": self.rerank_model,
            "rerank_endpoint": self.rerank_endpoint,
            "rerank_error": None,
            "candidate_count": len(docs_with_rank),
        }

        if not docs_with_rank or not self.rerank_enabled:
            return docs_with_rank[:top_k], meta

        # 准备请求数据
        payload = {
            "model": self.rerank_model,
            "query": query,
            "documents": [doc.get("text", doc.get("content", "")) for doc in docs_with_rank],
            "top_n": min(top_k, len(docs_with_rank)),
            "return_documents": False,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.rerank_api_key}",
        }

        try:
            meta["rerank_applied"] = True
            logger.info(f"[Rerank] 开始，{len(docs_with_rank)} 条文档，top_k={top_k}")

            response = requests.post(
                self.rerank_endpoint,
                headers=headers,
                json=payload,
                timeout=self.rerank_timeout,
            )

            if response.status_code >= 400:
                meta["rerank_error"] = f"HTTP {response.status_code}: {response.text}"
                logger.warning(f"[Rerank] API 返回错误: {meta['rerank_error']}，降级为原始排序")
                return self._fallback_sort(docs_with_rank, top_k), meta

            items = response.json().get("results", [])
            reranked = []
            for item in items:
                idx = item.get("index")
                if isinstance(idx, int) and 0 <= idx < len(docs_with_rank):
                    doc = dict(docs_with_rank[idx])
                    score = item.get("relevance_score")
                    if score is not None:
                        doc["rerank_score"] = score
                    reranked.append(doc)

            if reranked:
                logger.info(f"[Rerank] 完成，成功重排序 {len(reranked)} 条文档")
                return reranked[:top_k], meta

            meta["rerank_error"] = "empty_rerank_results"
            logger.warning(f"[Rerank] 返回结果为空，降级为原始排序")
            return self._fallback_sort(docs_with_rank, top_k), meta

        except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            meta["rerank_error"] = str(e)
            logger.error(f"[Rerank] 调用失败: {e}，降级为原始排序")
            return self._fallback_sort(docs_with_rank, top_k), meta

    def _fallback_sort(self, docs: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """
        降级排序：按原始 score 降序排列
        """
        return sorted(
            docs,
            key=lambda c: c.get("score", c.get("rerank_score", 0.0)),
            reverse=True,
        )[:top_k]


_rerank_service = None


def get_rerank_service() -> RerankService:
    global _rerank_service
    if _rerank_service is None:
        _rerank_service = RerankService()
    return _rerank_service
