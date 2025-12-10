import json
import os
import re
from typing import List, Optional

import requests

try:
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover - optional dependency
    BM25Okapi = None

try:
    import jieba
except Exception:  # pragma: no cover - optional dependency
    jieba = None

from utils import log_title
from rag.vector_store_faiss import FaissVectorStore
from rag.chunk.recursive import RecursiveCharacterTextSplitter


class EmbeddingRetriever:
    """
    Embedding 服务封装。
    
    支持两种模式：
    1. OpenAI 兼容 API（包括 OpenAI 官方、DeepBricks 等）
    2. Ollama 原生 API
    
    配置优先级：
    - 构造函数参数 > 环境变量
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        chunking_strategy: str = "whole",  # "whole" or "recursive"
        vector_store_config: Optional[dict] = None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.chunking_strategy = chunking_strategy
        self.vector_store_config = vector_store_config or {}
        backend = self.vector_store_config.get("backend", "faiss")
        self.vector_store = self._init_vector_store(backend)
        self.documents_buffer: List[str] = []
        self.bm25 = None
        self.last_scores: List[dict] = []
        
        # 初始化切分器
        self.recursive_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        
        # 确定使用哪种 API
        self._detect_api_type()

    def _detect_api_type(self) -> None:
        """检测应该使用哪种 API"""
        # 优先使用传入的参数
        if self.base_url:
            # 如果 URL 包含 /v1，认为是 OpenAI 兼容格式
            if "/v1" in self.base_url:
                self._api_type = "openai"
                self._endpoint = f"{self.base_url.rstrip('/')}/embeddings"
            else:
                # 否则认为是 Ollama 原生格式
                self._api_type = "ollama"
                self._endpoint = f"{self.base_url.rstrip('/')}/api/embeddings"
            return
        
        # 回退到环境变量
        openai_url = os.environ.get("EMBEDDING_BASE_URL")
        openai_key = os.environ.get("EMBEDDING_KEY")
        ollama_url = os.environ.get("OLLAMA_EMBED_BASE_URL")
        
        if openai_url and openai_key:
            self._api_type = "openai"
            self._endpoint = f"{openai_url.rstrip('/')}/embeddings"
            self.api_key = openai_key
        elif ollama_url:
            self._api_type = "ollama"
            self._endpoint = f"{ollama_url.rstrip('/')}/api/embeddings"
        else:
            raise RuntimeError(
                "Embedding 配置缺失。请设置以下任一组合：\n"
                "1. 构造函数传入 base_url\n"
                "2. 环境变量 EMBEDDING_BASE_URL + EMBEDDING_KEY\n"
                "3. 环境变量 OLLAMA_EMBED_BASE_URL"
            )

    def embed_document(self, document: str) -> Optional[List[float]]:
        log_title("EMBEDDING DOCUMENT")
        
        chunks = []
        # Check strategy (default to whole if not set)
        strategy = getattr(self, 'chunking_strategy', 'whole')
        
        if strategy == "recursive":
            chunks = self.recursive_splitter.split_text(document)
            print(f"  - Splitting document into {len(chunks)} chunks (Recursive)")
        else:
            chunks = [document]
            print(f"  - Using whole document as 1 chunk (Default)")
            
        last_embedding = None
        for chunk in chunks:
            if not chunk.strip():
                continue
            embedding = self._embed(chunk)
            self._ensure_vector_store_initialized(embedding)
            self.vector_store.add_embedding(embedding, chunk)
            self.documents_buffer.append(chunk)
            last_embedding = embedding
            
        return last_embedding

    def embed_query(self, query: str) -> List[float]:
        log_title("EMBEDDING QUERY")
        return self._embed(query)

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        self.last_scores = []
        query_embedding = self.embed_query(query)
        if not self.vector_store:
            return []
        # 如果还没有文档被添加，返回空
        if getattr(self.vector_store, "size", None) and self.vector_store.size() == 0:
            return []
        vector_results_with_scores = self.vector_store.search_with_scores(query_embedding, top_k)
        vector_results = [doc for doc, _ in vector_results_with_scores]

        # 确保 BM25 已构建
        if not self.bm25 and self.documents_buffer:
            self.build_keyword_index()
        keyword_results_with_scores = self.retrieve_keyword_with_scores(query, top_k)
        keyword_results = [doc for doc, _ in keyword_results_with_scores]

        # prepare fusion records
        fused_records: List[dict] = []
        vector_rank = {doc: rank for rank, (doc, _) in enumerate(vector_results_with_scores)}
        keyword_rank = {doc: rank for rank, (doc, _) in enumerate(keyword_results_with_scores)}
        all_docs = list(dict.fromkeys(vector_results + keyword_results))

        if vector_results and keyword_results:
            fused_docs = self._rrf_fusion(vector_results, keyword_results)
        else:
            fused_docs = vector_results if vector_results else keyword_results

        for doc in fused_docs:
            v_score = next((s for d, s in vector_results_with_scores if d == doc), None)
            k_score = next((s for d, s in keyword_results_with_scores if d == doc), None)
            v_r = vector_rank.get(doc)
            k_r = keyword_rank.get(doc)
            fused_score = 0.0
            if v_r is not None:
                fused_score += 1 / (60 + v_r + 1)
            if k_r is not None:
                fused_score += 1 / (60 + k_r + 1)
            fused_records.append(
                {
                    "doc": doc,
                    "vector_score": v_score,
                    "keyword_score": k_score,
                    "fused_score": fused_score,
                }
            )

        fused_records.sort(key=lambda x: x["fused_score"], reverse=True)
        self.last_scores = fused_records

        return [rec["doc"] for rec in fused_records[:top_k]]

    def _embed(self, text: str) -> List[float]:
        if self._api_type == "openai":
            return self._embed_openai(text)
        else:
            return self._embed_ollama(text)

    def _embed_openai(self, text: str) -> List[float]:
        """OpenAI 兼容 API 格式"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        response = requests.post(
            self._endpoint,
            headers=headers,
            json={
                "model": self.model,
                "input": text,
                "encoding_format": "float",
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    def _embed_ollama(self, text: str) -> List[float]:
        """Ollama 原生 API 格式"""
        response = requests.post(
            self._endpoint,
            headers={"Content-Type": "application/json"},
            json={
                "model": self.model,
                "prompt": text,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["embedding"]

    def _init_vector_store(self, backend: str):
        backend = backend.lower()
        if backend == "faiss":
            store = FaissVectorStore(
                index_factory=self.vector_store_config.get("index_factory", "Flat"),
                persist_path=self.vector_store_config.get("path"),
                metadata_path=self.vector_store_config.get("meta_path"),
            )
            try:
                store.load()
            except Exception:
                pass
            return store
        raise RuntimeError(f"Unsupported vector store backend '{backend}'. Only 'faiss' is supported now.")

    def _ensure_vector_store_initialized(self, embedding: List[float]) -> None:
        # 对内存版无需处理；faiss 会在添加时创建索引
        if isinstance(self.vector_store, FaissVectorStore) and self.vector_store.dim is None:
            # 创建索引时会用传入的 embedding 维度
            self.vector_store._ensure_index(len(embedding), self.vector_store._require_faiss()[0])

    def save_if_possible(self) -> None:
        """
        Persist index/metadata for backends that support it (e.g., FAISS).
        """
        if isinstance(self.vector_store, FaissVectorStore):
            try:
                self.vector_store.save()
                log_title("VECTOR STORE")
                print("FAISS index saved.")
            except Exception as exc:
                log_title("VECTOR STORE")
                print(f"Failed to save FAISS index: {exc}")

    def set_meta_info(self, embedding_model: str, chunk_strategy: str, data_signature: str = "") -> None:
        if isinstance(self.vector_store, FaissVectorStore):
            self.vector_store.set_meta_info(embedding_model, chunk_strategy, data_signature)

    def ensure_compatibility(self, embedding_model: str, chunk_strategy: str, data_signature: str = "") -> None:
        """
        If existing FAISS index meta mismatches, reset and rebuild.
        """
        if isinstance(self.vector_store, FaissVectorStore):
            if not self.vector_store.is_compatible(embedding_model, chunk_strategy, data_signature):
                self.vector_store.reset()

    def has_ready_index(self, embedding_model: str, chunk_strategy: str, data_signature: str = "") -> bool:
        """
        Return True if a FAISS index is loaded, non-empty, and meta matches.
        """
        if isinstance(self.vector_store, FaissVectorStore):
            if self.vector_store.is_compatible(embedding_model, chunk_strategy, data_signature):
                if getattr(self.vector_store, "size", None) and self.vector_store.size() > 0:
                    return True
        return False

    # --- Keyword / BM25 helpers ---
    def build_keyword_index(self) -> None:
        """
        Build BM25 index from buffered documents.
        """
        if not BM25Okapi:
            print("Warning: rank_bm25 is not installed; keyword search disabled.")
            return
        if not self.documents_buffer:
            return
        tokenized_corpus = [self._tokenize(doc) for doc in self.documents_buffer]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def retrieve_keyword(self, query: str, top_k: int = 3) -> List[str]:
        return [doc for doc, _ in self.retrieve_keyword_with_scores(query, top_k)]

    def retrieve_keyword_with_scores(self, query: str, top_k: int = 3) -> List[tuple[str, float]]:
        if not self.bm25:
            return []
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        scored_docs = list(zip(self.documents_buffer, scores))
        scored_docs = [(doc, float(score)) for doc, score in scored_docs if score > 0]
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return scored_docs[:top_k]

    def _rrf_fusion(self, vector_results: List[str], keyword_results: List[str], k: int = 60) -> List[str]:
        """
        Reciprocal Rank Fusion to merge vector and keyword rankings.
        """
        scores = {}
        for rank, doc in enumerate(vector_results):
            scores[doc] = scores.get(doc, 0.0) + 1 / (k + rank + 1)
        for rank, doc in enumerate(keyword_results):
            scores[doc] = scores.get(doc, 0.0) + 1 / (k + rank + 1)
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in sorted_docs]

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text with jieba if available; fallback to simple word split.
        """
        if jieba:
            return [tok for tok in jieba.cut(text) if tok.strip()]
        # fallback: mix of latin words and basic CJK ranges
        return [tok for tok in re.findall(r"[\\u4e00-\\u9fff]+|\\w+", text.lower()) if tok]
