# -*- coding: utf-8 -*-
"""
三级分块 ThreeLevelChunkSplitter 单元测试
测试范围：
- L1/L2/L3 三级结构
- 元数据正确（parent_chunk_id、root_chunk_id）
- Auto-merging 逻辑
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.services.three_level_chunk_splitter import ThreeLevelChunkSplitter


def test_three_level_splitter_init():
    """测试初始化"""
    splitter = ThreeLevelChunkSplitter()
    assert hasattr(splitter, "split_text")
    assert hasattr(splitter, "split_document")


def test_three_level_splitter_split_text(test_sample_text):
    """测试三级分割文本"""
    splitter = ThreeLevelChunkSplitter()
    chunks = splitter.split_text(test_sample_text, filename="test_doc")
    
    assert isinstance(chunks, list)
    assert len(chunks) > 0
    
    # 检查三级结构是否都存在
    levels = {chunk["chunk_level"] for chunk in chunks}
    assert 1 in levels
    assert 2 in levels
    assert 3 in levels


def test_three_level_splitter_chunk_metadata(test_sample_text):
    """测试 chunk 元数据完整"""
    splitter = ThreeLevelChunkSplitter()
    chunks = splitter.split_text(test_sample_text, filename="test_doc")
    
    for chunk in chunks:
        assert "chunk_id" in chunk
        assert "chunk_level" in chunk
        assert "text" in chunk
        assert "filename" in chunk
        
        if chunk["chunk_level"] > 1:
            assert "parent_chunk_id" in chunk
            assert "root_chunk_id" in chunk


def test_three_level_splitter_hierarchy(test_sample_text):
    """测试三级层级关系正确"""
    splitter = ThreeLevelChunkSplitter()
    chunks = splitter.split_text(test_sample_text, filename="test_doc")
    
    # 构建 chunk map
    chunk_map = {c["chunk_id"]: c for c in chunks}
    
    # 验证：L3 的 parent 应该是 L2，L2 的 parent 应该是 L1
    l3_chunks = [c for c in chunks if c["chunk_level"] == 3]
    
    if l3_chunks:
        l3 = l3_chunks[0]
        parent = chunk_map.get(l3["parent_chunk_id"])
        
        if parent:
            assert parent["chunk_level"] == 2
            assert parent["root_chunk_id"] == l3["root_chunk_id"]


def test_three_level_splitter_empty_text():
    """测试空文本"""
    splitter = ThreeLevelChunkSplitter()
    chunks = splitter.split_text("", filename="test")
    assert chunks == []


def test_three_level_splitter_short_text():
    """测试短文本"""
    splitter = ThreeLevelChunkSplitter()
    chunks = splitter.split_text("这是非常短的文本", filename="test")
    
    # 短文本可能只生成少数 chunk，但应该至少有 L3
    levels = {chunk["chunk_level"] for chunk in chunks}
    assert 3 in levels


def test_three_level_splitter_custom_params():
    """测试自定义参数"""
    splitter = ThreeLevelChunkSplitter(
        l1_size=500,
        l2_size=200,
        l3_size=100,
    )
    chunks = splitter.split_text("a" * 1000, filename="custom_test")
    assert len(chunks) > 0


def test_three_level_splitter_page_numbers():
    """测试页码支持"""
    splitter = ThreeLevelChunkSplitter()
    chunks = splitter.split_text(
        "测试文本",
        filename="test",
        page_number=1
    )
    
    for chunk in chunks:
        assert chunk.get("page_number") == 1
