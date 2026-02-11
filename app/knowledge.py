"""RAG 知识库模块 - 文档分块与检索"""
import re
import math
from typing import List, Dict, Optional
from collections import Counter


class KnowledgeStore:
    """基于内存的知识库存储与检索"""

    def __init__(self):
        self._documents: Dict[str, List[str]] = {}  # filename -> chunks

    def upload(self, filename: str, content: str, chunk_size: int = 300, overlap: int = 80) -> int:
        """
        上传文档并分块
        返回分块数量
        优先按段落分块，再按大小切分
        """
        chunks = self._split_chunks(content, chunk_size, overlap)
        self._documents[filename] = chunks
        return len(chunks)

    def _split_chunks(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """智能分块：优先按段落/换行分割，保持语义完整性"""
        # 先按段落分割（双换行或单换行）
        paragraphs = re.split(r'\n\s*\n|\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            # 如果当前段落本身就超过 chunk_size，按大小切分
            if len(para) > chunk_size:
                # 先把 current_chunk 存入
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                # 对超长段落按句子边界切分
                sentences = re.split(r'([。！？；\n])', para)
                temp = ""
                for i, seg in enumerate(sentences):
                    if len(temp) + len(seg) <= chunk_size:
                        temp += seg
                    else:
                        if temp.strip():
                            chunks.append(temp.strip())
                        temp = seg
                if temp.strip():
                    chunks.append(temp.strip())
            elif len(current_chunk) + len(para) + 1 <= chunk_size:
                # 可以合并到当前块
                if current_chunk:
                    current_chunk += "\n" + para
                else:
                    current_chunk = para
            else:
                # 当前块已满，开始新块
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = para

        # 处理最后一个块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # 如果没有产生任何块（比如文本没有换行），按传统方式切分
        if not chunks:
            chunks = self._split_by_size(text, chunk_size, overlap)

        return chunks

    def _split_by_size(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """回退方案：按固定大小分块"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap
            if start >= len(text):
                break
        return chunks

    def search(self, query: str, top_k: int = 3) -> List[str]:
        """
        混合检索策略：
        1. 子串直接匹配（最高权重）
        2. 关键短语匹配
        3. TF-IDF 词项匹配（兜底）
        返回最相关的 top_k 个片段
        """
        if not self._documents:
            return []

        # 收集所有 chunks
        all_chunks = []
        for filename, chunks in self._documents.items():
            all_chunks.extend(chunks)

        if not all_chunks:
            return []

        query_lower = query.lower().strip()

        # === 策略 1: 子串匹配 ===
        # 提取查询中的关键短语（去掉常见疑问词和语气词）
        key_phrases = self._extract_key_phrases(query)

        scored_chunks = []
        for chunk in all_chunks:
            chunk_lower = chunk.lower()
            score = 0.0

            # 子串直接命中（最高权重）
            for phrase in key_phrases:
                if phrase in chunk_lower:
                    # 越长的短语命中，权重越高
                    score += len(phrase) * 10

            # === 策略 2: N-gram 匹配 ===
            query_ngrams = self._get_ngrams(query_lower, 2, 5)
            for ngram in query_ngrams:
                if ngram in chunk_lower:
                    score += len(ngram) * 2

            # === 策略 3: 关键词 TF-IDF ===
            query_terms = self._tokenize(query)
            if query_terms:
                doc_count = len(all_chunks)
                for term in query_terms:
                    if term in chunk_lower:
                        # IDF 加权
                        df = sum(1 for c in all_chunks if term in c.lower())
                        idf = math.log((doc_count + 1) / (df + 1)) + 1
                        tf = chunk_lower.count(term)
                        score += tf * idf

            if score > 0:
                scored_chunks.append((score, chunk))

        # 按分数降序排序，取 top_k
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[:top_k]]

    def _extract_key_phrases(self, query: str) -> List[str]:
        """从查询中提取关键短语，去掉疑问词和语气词"""
        query = query.lower().strip()
        # 去掉常见的疑问词和语气词
        stop_patterns = [
            r'吗$', r'呢$', r'啊$', r'呀$', r'嘛$', r'吧$',
            r'^请问', r'^请', r'^你好',
            r'是什么', r'是多少', r'怎么样', r'如何',
            r'可以.{0,2}吗', r'能不能', r'是否',
            r'有没有', r'有哪些', r'什么是',
        ]

        cleaned = query
        for pattern in stop_patterns:
            cleaned = re.sub(pattern, '', cleaned)
        cleaned = cleaned.strip()

        phrases = []
        # 原始查询（去语气词后）作为一个短语
        if cleaned and len(cleaned) >= 2:
            phrases.append(cleaned)

        # 提取数字+中文的组合（如 "6岁以下"）
        num_phrases = re.findall(r'\d+[\u4e00-\u9fff]+', query)
        phrases.extend(num_phrases)

        # 提取连续中文短语（3-8字）
        cn_phrases = re.findall(r'[\u4e00-\u9fff]{3,8}', query)
        phrases.extend(cn_phrases)

        # 去重
        seen = set()
        unique = []
        for p in phrases:
            if p not in seen:
                seen.add(p)
                unique.append(p)

        return unique

    def _get_ngrams(self, text: str, min_n: int = 2, max_n: int = 5) -> List[str]:
        """生成字符级 n-gram"""
        # 去掉空白和标点
        clean = re.sub(r'[^\u4e00-\u9fff\w]', '', text)
        ngrams = []
        for n in range(min_n, max_n + 1):
            for i in range(len(clean) - n + 1):
                ngrams.append(clean[i:i+n])
        return ngrams

    def _tokenize(self, text: str) -> List[str]:
        """改进分词：提取中文字符、短语、数字组合和英文单词"""
        text = text.lower()
        tokens = []
        # 提取英文单词
        tokens.extend(re.findall(r'[a-zA-Z]+', text))
        # 提取数字（含与中文的组合如 "6岁"）
        tokens.extend(re.findall(r'\d+', text))
        # 提取数字+中文组合
        tokens.extend(re.findall(r'\d+[\u4e00-\u9fff]+', text))
        # 提取中文短语（2-6字，更长的短语更有区分度）
        tokens.extend(re.findall(r'[\u4e00-\u9fff]{2,6}', text))
        # 提取单个中文字符（低权重兜底）
        tokens.extend(re.findall(r'[\u4e00-\u9fff]', text))
        # 去重但保留顺序
        seen = set()
        unique = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique

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
