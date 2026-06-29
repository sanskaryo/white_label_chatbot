# WHAT DOES THIS FILE DO: Hybrid RAG service combining vector search, BM25, and cross-encoder reranking

# ================== IMPORTS ==================
import json
import logging
import re
import threading
import time
from collections import OrderedDict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
from openai import AzureOpenAI

try:
    from sentence_transformers import CrossEncoder
    HAS_RERANKER = True
except Exception:
    CrossEncoder = None
    HAS_RERANKER = False

from config import (
    FOUNDRY_ENDPOINT, FOUNDRY_API_KEY, FOUNDRY_DEPLOYMENT, AZURE_EMBEDDING_MODEL,
    QUERY_EMBED_CACHE_SIZE, QUERY_EMBED_CACHE_TTL_SEC, RERANK_SKIP_TOP1, RERANK_SKIP_GAP,
    CHUNK_MAX_CHARS, CHUNK_OVERLAP, ENABLE_RERANKING, HYBRID_VECTOR_WEIGHT, HYBRID_BM25_WEIGHT,
    MAX_COMPLETION_TOKENS,
)
from utils.helpers import normalize_azure_endpoint, _secs
from utils.security import sanitize_input, sanitize_response
from workflow_db import get_system_setting
# ================== IMPORTS ==================


# =========== VARIABLES : logging ===========
logger = logging.getLogger("white_label")
# =========== VARIABLES : logging ===========


# =========== RAG SERVICE ===========
class RAGService:
    ''' Hybrid RAG engine combining vector search, BM25, and cross-encoder reranking '''

    def __init__(self):
        ''' Initialize RAG service with embeddings, BM25, and Azure OpenAI client '''

        # FLOW-1: Initialize in-memory document and embedding storage
        self.documents = []
        self.embeddings = []
        self.document_tokens = []
        self.bm25 = None
        self._runtime_index_lock = threading.RLock()
        self._bm25_lock = threading.RLock()

        # FLOW-2: Initialize query embedding cache with LRU eviction
        self._query_embed_cache_size = QUERY_EMBED_CACHE_SIZE
        self._query_embed_cache_ttl_sec = QUERY_EMBED_CACHE_TTL_SEC
        self._query_embed_cache = OrderedDict()  # USE: OrderedDict for LRU cache tracking
        self._query_embed_cache_lock = threading.RLock()

        # FLOW-3: Store reranking configuration
        self._rerank_skip_top1 = RERANK_SKIP_TOP1
        self._rerank_skip_gap = RERANK_SKIP_GAP

        # FLOW-4: Initialize Azure OpenAI client for embeddings and LLM calls
        self.azure_client = AzureOpenAI(
            api_version="2024-02-01",
            azure_endpoint=normalize_azure_endpoint(FOUNDRY_ENDPOINT),
            api_key=FOUNDRY_API_KEY,
        )

        # FLOW-5: Try to load cross-encoder reranker if available and enabled
        self.reranker = None
        if HAS_RERANKER and ENABLE_RERANKING:
            try:
                self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                logger.info("Cross-Encoder reranker loaded")
            except Exception as exc:
                logger.warning(f"Failed to load reranker: {exc}")
                self.reranker = None

    def extend_runtime_index(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]) -> int:
        ''' Add documents and embeddings to in-memory index and rebuild BM25; return count added '''

        # FLOW-1: Return 0 if inputs empty or None
        if not documents or not embeddings:
            return 0

        # FLOW-2: Convert embeddings to numpy array with float dtype
        emb_array = np.array(embeddings, dtype=float)
        if emb_array.ndim == 1:
            emb_array = emb_array.reshape(1, -1)

        # FLOW-3: Validate embeddings and documents count match
        if emb_array.shape[0] != len(documents):
            raise ValueError("Documents and embeddings count mismatch")

        # FLOW-4: Update index under lock to prevent race conditions
        with self._runtime_index_lock:
            # FLOW-5: Initialize embeddings array or append if already populated
            if isinstance(self.embeddings, list) and len(self.embeddings) == 0:
                self.embeddings = emb_array
            elif getattr(self.embeddings, "ndim", 0) == 1 and len(self.embeddings) == 0:
                self.embeddings = emb_array
            else:
                # FLOW-6: Verify embedding dimensions match when appending
                if self.embeddings.shape[1] != emb_array.shape[1]:
                    raise ValueError("Embedding dimension mismatch")
                self.embeddings = np.vstack([self.embeddings, emb_array])  # USE: vstack for appending arrays

            # FLOW-7: Add documents and rebuild BM25 index
            self.documents.extend(documents)
            self._build_bm25_index()

        return len(documents)

    # ROLE: Remove all chunks belonging to a specific upload from the runtime index
    def remove_upload_from_index(self, upload_id: int) -> int:
        ''' Delete chunks by upload_id and rebuild BM25; return count removed '''

        # FLOW-1: Build URL prefix for the upload to identify chunks to remove
        prefix = f"upload://{upload_id}/"
        removed_count = 0

        # FLOW-2: Acquire lock and check if documents exist
        with self._runtime_index_lock:
            if not self.documents:
                return 0

            # FLOW-3: Identify indices of documents to keep (not from this upload)
            keep_indices = []
            for i, doc in enumerate(self.documents):
                if not doc.get("url", "").startswith(prefix):
                    keep_indices.append(i)
                else:
                    removed_count += 1

            # FLOW-4: Rebuild indices if any documents were removed
            if removed_count > 0:
                # FLOW-5: Filter documents and embeddings to keep only non-matching entries
                self.documents = [self.documents[i] for i in keep_indices]
                if getattr(self.embeddings, "ndim", 0) > 0 and len(self.embeddings) > 0:
                    self.embeddings = self.embeddings[keep_indices]  # USE: NumPy indexing for filtering

                # FLOW-6: Rebuild BM25 index after removal
                self._build_bm25_index()

        return removed_count

    # ROLE: Split text into overlapping chunks respecting sentence boundaries
    @staticmethod
    def split_text(text: str, max_chars: int = CHUNK_MAX_CHARS, overlap: int = CHUNK_OVERLAP) -> List[str]:
        ''' Split text into chunks: try para + sentence boundaries, fall back to character splitting '''

        # FLOW-1: Return empty list if text empty
        if not text:
            return []

        # FLOW-2: Split by paragraph boundaries (double newline) and normalize whitespace
        paragraphs = re.split(r'\n{2,}', text)
        paragraphs = [" ".join(p.split()) for p in paragraphs if p.strip()]
        if not paragraphs:
            return []

        # FLOW-3: Define helper to split paragraph into sentences while respecting max_chars
        def _sentence_split(para: str) -> List[str]:
            ''' Split paragraph into sentences, combining to fill max_chars limit '''

            sentences: List[str] = []
            raw_sents = re.split(r'(?<=[.!?])\s+', para)  # USE: Regex lookbehind for sentence boundaries
            buf = ""
            for sent in raw_sents:
                if not buf:
                    buf = sent
                elif len(buf) + 1 + len(sent) <= max_chars:
                    buf += " " + sent
                else:
                    if buf:
                        sentences.append(buf)
                    buf = sent
            if buf:
                sentences.append(buf)

            return sentences

        # FLOW-4: Define helper to split oversized text by character with overlap
        def _char_split(text_block: str) -> List[str]:
            ''' Split text by characters with overlap for very long sentences '''

            parts: List[str] = []
            start = 0
            while start < len(text_block):
                end = min(start + max_chars, len(text_block))
                parts.append(text_block[start:end].strip())
                if end >= len(text_block):
                    break
                start = max(0, end - overlap)  # USE: Sliding window with overlap

            return [p for p in parts if p]

        # FLOW-5: Initialize chunks list and buffer for paragraph merging
        chunks: List[str] = []
        buffer = ""

        # FLOW-6: Process each paragraph - try to merge with buffer or use sentence splitting
        for para in paragraphs:
            # FLOW-7: If para fits in max_chars, try to merge with buffer
            if len(para) <= max_chars:
                if not buffer:
                    buffer = para
                elif len(buffer) + 2 + len(para) <= max_chars:
                    buffer += "\n\n" + para
                else:
                    if buffer:
                        chunks.append(buffer)
                    buffer = para
            else:
                # FLOW-8: Para too large - flush buffer and split para by sentences
                if buffer:
                    chunks.append(buffer)
                    buffer = ""

                sents = _sentence_split(para)
                sent_buf = ""

                # FLOW-9: Build sentences into chunks or use character splitting for oversized sentences
                for sent in sents:
                    if len(sent) > max_chars:
                        if sent_buf:
                            chunks.append(sent_buf)
                            sent_buf = ""
                        chunks.extend(_char_split(sent))  # USE: Fallback to character splitting
                    elif not sent_buf:
                        sent_buf = sent
                    elif len(sent_buf) + 1 + len(sent) <= max_chars:
                        sent_buf += " " + sent
                    else:
                        chunks.append(sent_buf)
                        sent_buf = sent

                if sent_buf:
                    chunks.append(sent_buf)

        # FLOW-10: Flush remaining buffer
        if buffer:
            chunks.append(buffer)

        # FLOW-11: Apply overlap to adjacent chunks if overlap > 0
        if overlap > 0 and len(chunks) > 1:
            overlapped: List[str] = [chunks[0]]
            for i in range(1, len(chunks)):
                prev_tail = chunks[i - 1][-overlap:].strip()
                merged = prev_tail + " " + chunks[i] if prev_tail else chunks[i]
                if len(merged) <= max_chars + overlap:
                    overlapped.append(merged)
                else:
                    overlapped.append(chunks[i])

            return [c for c in overlapped if c.strip()]

        return [c for c in chunks if c.strip()]

    # ROLE: Tokenize text for BM25 search by lowercasing and removing special characters
    @staticmethod
    def tokenize_text(text: str) -> List[str]:
        ''' Convert text to lowercase tokens, filter special chars and short tokens '''

        # FLOW-1: Lowercase all text
        cleaned = text.lower()

        # FLOW-2: Remove special characters, keeping only alphanumeric and spaces
        cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)  # USE: Regex for character class filtering

        # FLOW-3: Split into tokens and filter out single-character tokens
        tokens = [token for token in cleaned.split() if len(token) > 1]

        return tokens

    # ROLE: Build BM25 keyword search index from current documents
    def _build_bm25_index(self) -> None:
        ''' Tokenize all documents and create BM25 index for keyword search '''

        # FLOW-1: Acquire lock to prevent concurrent index building
        with self._bm25_lock:
            # FLOW-2: Tokenize all documents
            self.document_tokens = [self.tokenize_text(doc.get("text", "")) for doc in self.documents]

            # FLOW-3: Build BM25 index if any tokens exist
            if any(self.document_tokens):
                try:
                    self.bm25 = BM25Okapi(self.document_tokens)  # USE: BM25Okapi for keyword scoring
                except Exception as exc:
                    logger.warning(f"Failed to build BM25 index: {exc}")
                    self.bm25 = None
            else:
                self.bm25 = None

    # ROLE: Load knowledge embeddings from Supabase pgvector store on startup
    def load_embeddings_from_pgvector(self) -> bool:
        ''' Fetch all chunks from pgvector and populate runtime index; return success flag '''

        # Import here to avoid circular imports
        from pgvector_store import pgvector_store
        from config import PGVECTOR_ENABLED

        # FLOW-1: Return False if pgvector not enabled
        if not PGVECTOR_ENABLED:
            return False

        # FLOW-2: Fetch all chunks from pgvector via RPC
        try:
            t0 = time.perf_counter()
            rows = pgvector_store.get_all_chunks_via_rpc()

            # FLOW-3: Return False if pgvector returned no rows
            if not rows:
                logger.warning("pgvector returned 0 chunks")
                return False

            # FLOW-4: Extract embeddings and documents from rows
            embeddings_list = []
            documents_list = []
            for row in rows:
                emb = row.get("embedding")
                if emb is None:
                    continue

                # FLOW-5: Parse embedding if stored as JSON string
                if isinstance(emb, str):
                    emb = json.loads(emb)

                embeddings_list.append(emb)
                documents_list.append(pgvector_store.row_to_doc(row))

            # FLOW-6: Return False if no valid embeddings extracted
            if not embeddings_list:
                return False

            # FLOW-7: Load into runtime index and rebuild BM25
            self.embeddings = np.array(embeddings_list, dtype=float)
            self.documents = documents_list
            self._build_bm25_index()

            logger.info(f"pgvector startup: loaded {len(self.documents)} chunks in {_secs(t0)}s")
            return True

        except Exception as exc:
            logger.warning(f"pgvector startup load failed: {exc}")
            return False

    # ROLE: Perform hybrid search combining vector similarity, BM25, and cross-encoder reranking
    def search(self, query: str, top_k: int = 5, timings: Optional[dict] = None) -> List[dict]:
        ''' Return top-k documents ranked by hybrid score; track timing if requested '''

        # FLOW-1: Snapshot index under lock to avoid mutations during search
        with self._runtime_index_lock:
            embeddings_snapshot = np.array(self.embeddings) if len(self.embeddings) > 0 else np.array([])
            documents_snapshot = list(self.documents)

        # FLOW-2: Return empty if no documents indexed
        if len(embeddings_snapshot) == 0:
            return []

        # FLOW-3: Get query embedding from cache or Azure OpenAI
        query_key = " ".join(query.split())
        query_embedding = None
        cache_hit = False

        # FLOW-4: Try cache if enabled
        if self._query_embed_cache_size > 0:
            now = time.time()
            with self._query_embed_cache_lock:
                cached = self._query_embed_cache.get(query_key)
                if cached is not None:
                    cached_embedding, cached_ts = cached

                    # FLOW-5: Use cached embedding if still within TTL
                    if self._query_embed_cache_ttl_sec <= 0 or (now - cached_ts) <= self._query_embed_cache_ttl_sec:
                        query_embedding = cached_embedding
                        cache_hit = True
                        self._query_embed_cache.move_to_end(query_key)  # USE: Move to end for LRU tracking
                    else:
                        del self._query_embed_cache[query_key]

        # FLOW-6: Call Azure OpenAI if embedding not cached
        t0 = time.perf_counter()
        if query_embedding is None:
            query_resp = self.azure_client.embeddings.create(input=[query], model=AZURE_EMBEDDING_MODEL)
            query_embedding = query_resp.data[0].embedding

            # FLOW-7: Cache embedding if cache enabled
            if self._query_embed_cache_size > 0:
                now = time.time()
                with self._query_embed_cache_lock:
                    self._query_embed_cache[query_key] = (query_embedding, now)
                    self._query_embed_cache.move_to_end(query_key)

                    # FLOW-8: Evict oldest entry if cache size exceeded
                    while len(self._query_embed_cache) > self._query_embed_cache_size:
                        self._query_embed_cache.popitem(last=False)  # USE: popitem(last=False) for FIFO eviction

        # FLOW-9: Record embedding time if timings requested
        if timings is not None:
            timings["embed_query_ms"] = 0.0 if cache_hit else round((time.perf_counter() - t0) * 1000, 2)
            timings["embed_query_cache"] = "hit" if cache_hit else "miss"

        # FLOW-10: Compute cosine similarity between query and all documents
        t1 = time.perf_counter()
        similarities = cosine_similarity([query_embedding], embeddings_snapshot)[0]
        if timings is not None:
            timings["similarity_ms"] = round((time.perf_counter() - t1) * 1000, 2)

        # FLOW-11: Compute BM25 scores if index available
        bm25_scores_all = None
        if self.bm25 is not None:
            t_bm25 = time.perf_counter()
            query_tokens = self.tokenize_text(query)
            bm25_scores_all = self.bm25.get_scores(query_tokens) if query_tokens else [0.0] * len(documents_snapshot)
            if timings is not None:
                timings["bm25_ms"] = round((time.perf_counter() - t_bm25) * 1000, 2)

        # FLOW-12: Get top candidates from both vector and BM25 scoring
        candidate_pool = []
        vector_top = np.argsort(similarities)[-top_k * 4:][::-1]  # USE: Get top-k*4 to merge with BM25
        candidate_pool.extend(vector_top.tolist())
        if bm25_scores_all is not None:
            bm25_top = np.argsort(bm25_scores_all)[-top_k * 4:][::-1]
            candidate_pool.extend(bm25_top.tolist())

        # FLOW-13: Deduplicate candidate pool while preserving order
        candidate_indices = list(dict.fromkeys(candidate_pool))[: top_k * 4]  # USE: dict.fromkeys for O(n) dedup

        # FLOW-14: Compute hybrid score (normalized vector + BM25)
        t2 = time.perf_counter()
        candidates = []

        # FLOW-15: Calculate normalization bounds for score fusion
        bm25_max = max(bm25_scores_all) if bm25_scores_all is not None else 0.0
        sim_max = max(similarities) if len(similarities) else 0.0
        sim_min = min(similarities) if len(similarities) else 0.0
        sim_span = max(sim_max - sim_min, 1e-6)

        # FLOW-16: Build candidate dicts with fused scores
        for idx in candidate_indices:
            bm25_score = float(bm25_scores_all[idx]) if bm25_scores_all is not None else 0.0
            vector_score = float(similarities[idx])

            # FLOW-17: Normalize and fuse vector + BM25 scores or use vector only
            if bm25_scores_all is not None and bm25_max > 0:
                norm_vector = (vector_score - sim_min) / sim_span  # USE: Min-max normalization for vector
                norm_bm25 = bm25_score / (bm25_max + 1e-6)
                fused_score = HYBRID_VECTOR_WEIGHT * norm_vector + HYBRID_BM25_WEIGHT * norm_bm25
            else:
                fused_score = vector_score

            candidates.append({
                "text": documents_snapshot[idx]["text"],
                "url": documents_snapshot[idx].get("url", ""),
                "title": documents_snapshot[idx].get("title", ""),
                "category": documents_snapshot[idx].get("category", "general"),
                "section_type": documents_snapshot[idx].get("section_type", "general"),
                "score": float(fused_score),
                "vector_score": vector_score,
                "bm25_score": bm25_score,
            })

        if timings is not None:
            timings["build_candidates_ms"] = round((time.perf_counter() - t2) * 1000, 2)

        # FLOW-18: Apply cross-encoder reranking if available
        if self.reranker and candidates:
            top1 = float(candidates[0]["score"])
            top2 = float(candidates[1]["score"]) if len(candidates) > 1 else -1.0
            gap = top1 - top2 if top2 >= 0 else top1

            # FLOW-19: Skip reranking if top result confidence is high and gap large
            if top1 >= self._rerank_skip_top1 and gap >= self._rerank_skip_gap:
                if timings is not None:
                    timings["rerank_ms"] = 0.0
                    timings["rerank_status"] = "skipped"

                return self._deduplicate_chunks(candidates[:top_k])

            # FLOW-20: Run cross-encoder reranking and re-sort candidates
            t3 = time.perf_counter()
            texts = [c["text"] for c in candidates]
            pairs = [[query, text] for text in texts]
            rerank_scores = self.reranker.predict(pairs)  # USE: Cross-encoder for semantic ranking

            for candidate, score in zip(candidates, rerank_scores):
                candidate["score"] = float(score)

            candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)
            if timings is not None:
                timings["rerank_ms"] = round((time.perf_counter() - t3) * 1000, 2)
                timings["rerank_status"] = "ran"
        elif timings is not None:
            timings["rerank_ms"] = 0.0
            timings["rerank_status"] = "disabled"

        return self._deduplicate_chunks(candidates[:top_k])

    # ROLE: Remove near-duplicate chunks based on sequence similarity
    @staticmethod
    def _deduplicate_chunks(chunks: List[dict], similarity_threshold: float = 0.82) -> List[dict]:
        ''' Filter chunks to remove near-duplicates using sequence matching on first 220 chars '''

        # FLOW-1: Return early if 1 or fewer chunks
        if len(chunks) <= 1:
            return chunks

        # FLOW-2: Initialize unique list and tracking of seen chunk heads
        unique: List[dict] = []
        seen_heads: List[str] = []

        # FLOW-3: Check each chunk against seen heads for duplication
        for chunk in chunks:
            # FLOW-4: Extract first 220 chars as chunk "head" for comparison
            head = (chunk.get("text") or "")[:220]

            # FLOW-5: Check if head is similar to any seen head above threshold
            is_dup = any(SequenceMatcher(None, head, seen).ratio() >= similarity_threshold for seen in seen_heads)  # USE: SequenceMatcher for fuzzy comparison

            # FLOW-6: Add to unique list if not a duplicate
            if not is_dup:
                unique.append(chunk)
                seen_heads.append(head)

        return unique

    # ROLE: Generate answer using Azure OpenAI with RAG context and conversation history
    def generate_answer(self, question: str, context: str, timings: Optional[dict] = None, conversation_history: Optional[list] = None) -> str:
        ''' Call Azure OpenAI with system prompt, context, and history; return generated answer '''

        # Import here to avoid circular imports
        from core.middleware import get_cached_system_prompt, get_cached_llm_temperature

        # FLOW-1: Get current system prompt from cache
        system_prompt = get_cached_system_prompt()

        # FLOW-2: Format context or use fallback message if empty
        combined_context = f"Retrieved Content:\n{context}" if context else "No relevant content was found in the knowledge base."

        # FLOW-3: Initialize messages with system prompt
        messages = [{"role": "system", "content": system_prompt}]

        # FLOW-4: Add conversation history if provided (last 4 turns only)
        if conversation_history:
            for turn in conversation_history[-4:]:
                # FLOW-5: Extract role and content, handle both object and dict formats
                role = turn.role if hasattr(turn, "role") else turn.get("role", "")
                raw_content = turn.content if hasattr(turn, "content") else (turn.get("content") or "")
                content = sanitize_input(str(raw_content).strip())[:600]

                # FLOW-6: Add valid turns to messages
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        # FLOW-7: Append question with context
        messages.append({"role": "user", "content": f"Context:\n{combined_context}\n\nQuestion: {question}"})

        # FLOW-8: Get temperature setting and call Azure OpenAI
        _temperature = get_cached_llm_temperature()

        t0 = time.perf_counter()
        response = self.azure_client.chat.completions.create(
            model=FOUNDRY_DEPLOYMENT,
            messages=messages,
            temperature=_temperature,
            max_completion_tokens=MAX_COMPLETION_TOKENS,
        )

        # FLOW-9: Record completion time if timings requested
        if timings is not None:
            timings["chat_completion_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # FLOW-10: Extract and sanitize response text
        raw = response.choices[0].message.content.strip()
        return sanitize_response(raw)
# =========== RAG SERVICE ===========