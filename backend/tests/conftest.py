# -*- coding: utf-8 -*-
"""pytest 配置和 fixtures"""
import asyncio
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch

from fastapi.testclient import TestClient

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环 fixture"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings():
    """测试环境配置"""
    class TestSettings:
        environment = "test"
        database_url = "postgresql://test:test@localhost:5432/test_db"
        redis_url = "redis://localhost:6379/1"
        milvus_url = "http://localhost:19530"
    
    return TestSettings()


@pytest.fixture(scope="session")
def mock_cache():
    """Mock 缓存服务"""
    cache = Mock()
    cache.get_json = Mock(return_value=None)
    cache.set_json = Mock()
    cache.delete = Mock()
    return cache


@pytest.fixture(scope="function")
def mock_milvus_service():
    """Mock Milvus 服务"""
    milvus = Mock()
    milvus.hybrid_search = Mock(return_value=[{"text": "Test chunk", "score": 0.9}])
    milvus.dense_search = Mock(return_value=[{"text": "Test chunk", "score": 0.9}])
    milvus.upsert_chunks = Mock(return_value=True)
    return milvus


@pytest.fixture(scope="function")
def test_sample_text():
    """测试文本样本"""
    return """RAG 是 Retrieval-Augmented Generation 的缩写。
    它是一种将检索和生成结合的技术。
    首先从知识库中检索相关内容，然后使用 LLM 生成回答。
    这种方法既能利用外部知识，又能保持 LLM 的创造力。
    RAG 在企业知识库问答、客服等场景有广泛应用。"""


@pytest.fixture(scope="function")
def test_sample_table_data():
    """测试表格数据"""
    return [
        {"日期": "2024-01-01", "销量": 1000, "产品": "A"},
        {"日期": "2024-01-02", "销量": 1500, "产品": "B"},
    ]


@pytest.fixture(scope="session")
def test_jwt_secret():
    """测试 JWT Secret"""
    return "test-secret-key-for-jwt-generation-only"
