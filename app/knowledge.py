"""RAG 知识库模块 - 文档分块与检索"""
import re
import math
from typing import List, Dict, Optional
from collections import Counter


class KnowledgeStore:
    """基于内存的知识库存储与检索"""

    def __init__(self):
        self._documents: Dict[str, List[str]] = {}  # filename -> chunks

    def upload(self, filename: str, content: str, chunk_size: int = 500, overlap: int = 50) -> int:
        """
        上传文档并分块
        返回分块数量
        """
        chunks = self._split_chunks(content, chunk_size, overlap)
        self._documents[filename] = chunks
        return len(chunks)

    def _split_chunks(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """将文本按固定大小分块，相邻块有 overlap"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():  # 跳过空白块
                chunks.append(chunk.strip())
            start = end - overlap
            if start >= len(text):
                break
        return chunks

    def search(self, query: str, top_k: int = 3) -> List[str]:
        """
        基于 TF-IDF 相似度的简易检索
        返回最相关的 top_k 个片段
        """
        if not self._documents:
            return []

        # 分词（简单的中英文分词）
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # 收集所有 chunks
        all_chunks = []
        for filename, chunks in self._documents.items():
            all_chunks.extend(chunks)

        if not all_chunks:
            return []

        # 计算 IDF
        doc_count = len(all_chunks)
        idf = {}
        for term in query_terms:
            df = sum(1 for chunk in all_chunks if term in chunk.lower())
            idf[term] = math.log((doc_count + 1) / (df + 1)) + 1

        # 计算每个 chunk 的相关性得分
        scored_chunks = []
        for chunk in all_chunks:
            chunk_lower = chunk.lower()
            score = 0.0
            for term in query_terms:
                tf = chunk_lower.count(term)
                if tf > 0:
                    score += tf * idf.get(term, 1.0)
            if score > 0:
                scored_chunks.append((score, chunk))

        # 按分数降序排序，取 top_k
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[:top_k]]

    def _tokenize(self, text: str) -> List[str]:
        """简单分词：提取中文字符和英文单词"""
        text = text.lower()
        # 提取英文单词
        english_words = re.findall(r'[a-zA-Z]+', text)
        # 提取中文字符（单字作为 token）
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        # 提取连续中文短语（2-4字）
        chinese_phrases = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        return english_words + chinese_chars + chinese_phrases

    def has_documents(self) -> bool:
        """是否有已上传的文档"""
        return len(self._documents) > 0

    def get_stats(self) -> dict:
        """获取知识库统计信息"""
        total_chunks = sum(len(chunks) for chunks in self._documents.values())
        return {
            "documents": len(self._documents),
            "total_chunks": total_chunks,
            "filenames": list(self._documents.keys())
        }


# 全局知识库实例
knowledge_store = KnowledgeStore()
