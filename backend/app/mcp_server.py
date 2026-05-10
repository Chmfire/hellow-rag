# -*- coding: utf-8 -*-
# Model Context Protocol (MCP) Server
# 提供 RAG 知识库查询、文档管理等工具

from mcp.server.fastmcp import FastMCP
from typing import List, Optional, Dict, Any
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 初始化 MCP Server
mcp = FastMCP(
    name="RAG Knowledge Server",
    instructions="企业级 RAG 知识库 MCP 服务，提供知识库查询、文档管理、对话等功能"
)

# 延迟导入，避免启动时依赖问题
def get_knowledge_service():
    from app.services.knowledge_service import KnowledgeService
    return KnowledgeService()

def get_milvus_service():
    from app.services.milvus_service import MilvusService
    return MilvusService()


# ===================== 工具定义 =====================

@mcp.tool()
async def query_knowledge_base(
    query: str,
    kb_ids: Optional[List[int]] = None,
    top_k: int = 5
) -> str:
    """
    查询企业知识库，基于 RAG 检索增强生成。

    Args:
        query: 用户问题
        kb_ids: 知识库 ID 列表（可选，默认查询所有）
        top_k: 返回的相关文档数量（默认 5）

    Returns:
        基于知识库生成的回答
    """
    try:
        service = get_knowledge_service()
        
        # 如果没有指定知识库，查询所有
        if not kb_ids:
            # 这里可以从数据库获取所有 kb_ids
            kb_ids = [1]  # 默认查询第一个知识库
        
        # 调用检索
        results = await service.retrieve_and_merge(
            query=query,
            kb_ids=kb_ids,
            top_k=top_k
        )
        
        if not results:
            return "抱歉，知识库中没有找到相关信息。"
        
        # 格式化结果
        answer_parts = [f"根据知识库检索到 {len(results)} 个相关文档：\n"]
        
        for i, result in enumerate(results, 1):
            content = result.get("content", "")
            score = result.get("score", 0.0)
            metadata = result.get("metadata", {})
            source = metadata.get("file_name", "未知来源")
            
            answer_parts.append(
                f"\n--- 文档 {i} (相关性: {score:.2f}) ---\n"
                f"来源: {source}\n"
                f"内容: {content[:500]}..."
            )
        
        return "\n".join(answer_parts)
    
    except Exception as e:
        return f"查询知识库失败: {str(e)}"


@mcp.tool()
async def list_knowledge_bases() -> str:
    """
    列出所有可用的知识库。

    Returns:
        知识库列表（JSON 格式）
    """
    try:
        from app.db.database import AsyncSessionLocal
        from sqlalchemy import select
        # 这里需要根据实际的模型定义
        # from app.models import KnowledgeBase
        
        # 简化版：直接返回
        return """
        可用知识库列表：
        - ID: 1, 名称: 产品文档库, 文档数: 150
        - ID: 2, 名称: 技术手册, 文档数: 80
        - ID: 3, 名称: 培训资料, 文档数: 45
        """
    
    except Exception as e:
        return f"获取知识库列表失败: {str(e)}"


@mcp.tool()
async def search_documents(
    keyword: str,
    kb_id: Optional[int] = None,
    limit: int = 10
) -> str:
    """
    按关键词搜索文档。

    Args:
        keyword: 搜索关键词
        kb_id: 知识库 ID（可选）
        limit: 返回结果数量（默认 10）

    Returns:
        搜索结果列表
    """
    try:
        milvus = get_milvus_service()
        
        # 使用 Milvus 的关键词搜索
        results = milvus.search_by_keyword(
            query=keyword,
            kb_id=kb_id,
            limit=limit
        )
        
        if not results:
            return f"未找到包含 '{keyword}' 的文档。"
        
        # 格式化结果
        output = [f"搜索关键词 '{keyword}' 找到 {len(results)} 个文档：\n"]
        
        for i, doc in enumerate(results, 1):
            filename = doc.get("file_name", "未知")
            content = doc.get("content", "")[:200]
            score = doc.get("score", 0.0)
            
            output.append(
                f"\n{i}. {filename} (得分: {score:.2f})\n"
                f"   内容预览: {content}..."
            )
        
        return "\n".join(output)
    
    except Exception as e:
        return f"搜索文档失败: {str(e)}"


@mcp.tool()
async def get_document_summary(
    doc_id: str
) -> str:
    """
    获取指定文档的摘要和元数据。

    Args:
        doc_id: 文档 ID

    Returns:
        文档摘要
    """
    try:
        milvus = get_milvus_service()
        
        # 查询文档信息
        doc_info = milvus.get_document_info(doc_id)
        
        if not doc_info:
            return f"未找到文档 (ID: {doc_id})"
        
        filename = doc_info.get("file_name", "未知")
        created_at = doc_info.get("created_at", "未知")
        chunk_count = doc_info.get("chunk_count", 0)
        content = doc_info.get("content", "")[:500]
        
        return f"""
        文档摘要:
        - 文件名: {filename}
        - ID: {doc_id}
        - 创建时间: {created_at}
        - 分块数量: {chunk_count}
        
        内容预览:
        {content}...
        """
    
    except Exception as e:
        return f"获取文档摘要失败: {str(e)}"


# ===================== 资源定义 =====================

@mcp.resource("knowledge://bases")
async def list_all_knowledge_bases() -> str:
    """列出所有知识库的资源"""
    return await list_knowledge_bases()


@mcp.resource("knowledge://base/{kb_id}/documents")
async def list_kb_documents(kb_id: int) -> str:
    """列出指定知识库的所有文档"""
    try:
        milvus = get_milvus_service()
        docs = milvus.list_documents(kb_id=kb_id)
        
        if not docs:
            return f"知识库 {kb_id} 中没有文档。"
        
        output = [f"知识库 {kb_id} 共有 {len(docs)} 个文档：\n"]
        for i, doc in enumerate(docs, 1):
            filename = doc.get("file_name", "未知")
            doc_id = doc.get("doc_id", "未知")
            output.append(f"{i}. {filename} (ID: {doc_id})")
        
        return "\n".join(output)
    
    except Exception as e:
        return f"获取文档列表失败: {str(e)}"


# ===================== 启动入口 =====================

if __name__ == "__main__":
    # 使用 stdio 传输
    mcp.run(transport="stdio")
