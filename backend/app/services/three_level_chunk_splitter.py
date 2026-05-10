# -*- coding: utf-8 -*-
"""
三级分块器（用于 Auto-merging Retriever）
参考 SuperMew/document_loader.py 实现
支持三级滑动窗口分块，用于文档分块
"""
from typing import Dict, List
from langchain_text_splitters import RecursiveCharacterTextSplitter


class ThreeLevelChunkSplitter:
    """三级分块器，用于 Auto-merging Retriever"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        # 保留原有参数以兼容外部调用；默认启用三层滑动窗口分块。
        level_1_size = max(1200, chunk_size * 2)
        level_1_overlap = max(240, chunk_overlap * 2)
        level_2_size = max(600, chunk_size)
        level_2_overlap = max(120, chunk_overlap)
        level_3_size = max(300, chunk_size // 2)
        level_3_overlap = max(60, chunk_overlap // 2)

        self._splitter_level_1 = RecursiveCharacterTextSplitter(
            chunk_size=level_1_size,
            chunk_overlap=level_1_overlap,
            add_start_index=True,
            separators=["\n\n", "\n", "。", "！", "？", "，", "、", " ", ""],
        )
        self._splitter_level_2 = RecursiveCharacterTextSplitter(
            chunk_size=level_2_size,
            chunk_overlap=level_2_overlap,
            add_start_index=True,
            separators=["\n\n", "\n", "。", "！", "？", "，", "、", " ", ""],
        )
        self._splitter_level_3 = RecursiveCharacterTextSplitter(
            chunk_size=level_3_size,
            chunk_overlap=level_3_overlap,
            add_start_index=True,
            separators=["\n\n", "\n", "。", "！", "？", "，", "、", " ", ""],
        )

    @staticmethod
    def _build_chunk_id(filename: str, page_number: int, level: int, index: int) -> str:
        return f"{filename}::p{page_number}::l{level}::{index}"

    def _split_page_to_three_levels(
        self,
        text: str,
        base_doc: Dict,
        page_global_chunk_idx: int,
    ) -> List[Dict]:
        if not text:
            return []

        root_chunks: List[Dict] = []
        page_number = int(base_doc.get("page_number", 0))
        filename = base_doc["filename"]

        level_1_docs = self._splitter_level_1.create_documents([text], [base_doc])
        level_1_counter = 0
        level_2_counter = 0
        level_3_counter = 0

        for level_1_doc in level_1_docs:
            level_1_text = (level_1_doc.page_content or "").strip()
            if not level_1_text:
                continue
            level_1_id = self._build_chunk_id(filename, page_number, 1, level_1_counter)
            level_1_counter += 1

            level_1_chunk = {
                **base_doc,
                "text": level_1_text,
                "chunk_id": level_1_id,
                "parent_chunk_id": "",
                "root_chunk_id": level_1_id,
                "chunk_level": 1,
                "chunk_idx": page_global_chunk_idx,
            }
            page_global_chunk_idx += 1
            root_chunks.append(level_1_chunk)

            level_2_docs = self._splitter_level_2.create_documents([level_1_text], [base_doc])
            for level_2_doc in level_2_docs:
                level_2_text = (level_2_doc.page_content or "").strip()
                if not level_2_text:
                    continue
                level_2_id = self._build_chunk_id(filename, page_number, 2, level_2_counter)
                level_2_counter += 1

                level_2_chunk = {
                    **base_doc,
                    "text": level_2_text,
                    "chunk_id": level_2_id,
                    "parent_chunk_id": level_1_id,
                    "root_chunk_id": level_1_id,
                    "chunk_level": 2,
                    "chunk_idx": page_global_chunk_idx,
                }
                page_global_chunk_idx += 1
                root_chunks.append(level_2_chunk)

                level_3_docs = self._splitter_level_3.create_documents([level_2_text], [base_doc])
                for level_3_doc in level_3_docs:
                    level_3_text = (level_3_doc.page_content or "").strip()
                    if not level_3_text:
                        continue
                    level_3_id = self._build_chunk_id(filename, page_number, 3, level_3_counter)
                    level_3_counter += 1
                    root_chunks.append({
                        **base_doc,
                        "text": level_3_text,
                        "chunk_id": level_3_id,
                        "parent_chunk_id": level_2_id,
                        "root_chunk_id": level_1_id,
                        "chunk_level": 3,
                        "chunk_idx": page_global_chunk_idx,
                    })
                    page_global_chunk_idx += 1

        return root_chunks

    def split_text(
        self,
        text: str,
        filename: str = "unknown",
        file_path: str = "",
        file_type: str = "text",
        page_number: int = 0,
    ) -> List[dict]:
        """
        将文本切分为三级 chunks
        """
        if not text or not text.strip():
            return []

        base_doc = {
            "filename": filename,
            "file_path": file_path,
            "file_type": file_type,
            "page_number": page_number,
        }
        
        return self._split_page_to_three_levels(
            text=text.strip(),
            base_doc=base_doc,
            page_global_chunk_idx=0,
        )

    def split_text_with_metadata(
        self,
        text: str,
        base_metadata: dict = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> List[dict]:
        """返回带 metadata 的 chunk 列表，格式兼容现有系统"""
        filename = base_metadata.get("filename", "unknown") if base_metadata else "unknown"
        file_path = base_metadata.get("file_path", "") if base_metadata else ""
        file_type = base_metadata.get("file_type", "text") if base_metadata else "text"
        page_number = base_metadata.get("page_number", 0) if base_metadata else 0
        
        chunks = self.split_text(text, filename, file_path, file_type, page_number)
        
        # 转换为与 split_text_with_metadata 兼容的格式
        return [
            {
                "content": chunk["text"],
                "metadata": {
                    **(base_metadata or {}),
                    "chunk_index": chunk["chunk_idx"],
                    "chunk_id": chunk["chunk_id"],
                    "parent_chunk_id": chunk["parent_chunk_id"],
                    "root_chunk_id": chunk["root_chunk_id"],
                    "chunk_level": chunk["chunk_level"],
                }
            }
            for chunk in chunks
        ]
