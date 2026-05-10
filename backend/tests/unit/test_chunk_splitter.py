# -*- coding: utf-8 -*-
"""
Chunk Splitter 单元测试
测试范围：
- 基础文本分割
- 不同 chunk size 和 overlap 组合
- 边界条件（空文本、短文本）
- 元数据保留
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.services.chunk_splitter import split_text, split_text_with_metadata


def test_split_text_basic(test_sample_text):
    """测试基础文本分割"""
    chunks = split_text(test_sample_text, chunk_size=100, chunk_overlap=20)
    assert isinstance(chunks, list)
    assert len(chunks) > 0
    assert all(isinstance(chunk, str) for chunk in chunks)


def test_split_text_empty():
    """测试空文本"""
    chunks = split_text("", chunk_size=100, chunk_overlap=20)
    assert chunks == []


def test_split_text_short():
    """测试非常短的文本"""
    short_text = "这是一段很短的文本"
    chunks = split_text(short_text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) == 1
    assert short_text in chunks[0]


def test_split_text_size_variations():
    """测试不同 chunk size 组合"""
    text = "a" * 1000
    chunks_50 = split_text(text, chunk_size=50, chunk_overlap=10)
    chunks_200 = split_text(text, chunk_size=200, chunk_overlap=40)
    assert len(chunks_50) > len(chunks_200)


def test_split_text_overlap():
    """测试 overlap 生效"""
    text = "1234567890" * 10
    chunks = split_text(text, chunk_size=30, chunk_overlap=10)
    if len(chunks) >= 2:
        overlap_part = chunks[0][-10:]
        assert overlap_part in chunks[1]


def test_split_text_with_metadata(test_sample_text):
    """测试带元数据的分割"""
    metadata = {"source": "test", "doc_id": "123"}
    chunks = split_text_with_metadata(
        test_sample_text,
        base_metadata=metadata,
        chunk_size=100,
        chunk_overlap=20
    )
    
    assert isinstance(chunks, list)
    assert len(chunks) > 0
    
    for chunk in chunks:
        assert "text" in chunk
        assert "metadata" in chunk
        assert chunk["metadata"]["source"] == "test"
        assert chunk["metadata"]["doc_id"] == "123"


def test_split_text_with_metadata_empty():
    """测试带元数据的空文本"""
    chunks = split_text_with_metadata("", base_metadata={"test": "value"})
    assert chunks == []


def test_split_text_with_metadata_index():
    """测试 chunk index 正确"""
    text = "a" * 500
    chunks = split_text_with_metadata(
        text,
        base_metadata={"source": "test"},
        chunk_size=100,
        chunk_overlap=20
    )
    
    assert len(chunks) > 1
    for i, chunk in enumerate(chunks):
        assert "chunk_index" in chunk["metadata"]
        assert chunk["metadata"]["chunk_index"] == i
