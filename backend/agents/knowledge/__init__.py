# -*- coding: utf-8 -*-
from .graph import create_knowledge_agent
from .state import KnowledgeAgentState, RetrievedChunk, create_initial_state, RAGConfig

_agent = None
_stream_prep_agent = None


def get_knowledge_agent():
    """获取 Knowledge Agent 实例（使用 MemorySaver 避免 PostgreSQL 序列化开销）"""
    global _agent
    if _agent is None:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        _agent = create_knowledge_agent(checkpointer=checkpointer)
    return _agent


def get_knowledge_stream_prep_agent():
    """与 get_knowledge_agent 同构图，但在 generate_answer 前 interrupt，供 OpenAI 流式补全后恢复。"""
    global _stream_prep_agent
    if _stream_prep_agent is None:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        _stream_prep_agent = create_knowledge_agent(
            checkpointer=checkpointer,
            interrupt_before=["generate_answer"],
        )
    return _stream_prep_agent


__all__ = [
    "get_knowledge_agent",
    "get_knowledge_stream_prep_agent",
    "create_knowledge_agent",
    "KnowledgeAgentState",
    "RetrievedChunk",
    "create_initial_state",
    "RAGConfig",
]
