# WHAT DOES THIS FILE DO: thin wrapper around Supabase pgvector tables for storing and searching knowledge chunks (white-label version)

# ================== IMPORTS ==================
import logging
import json
from typing import Any, Dict, List, Optional
# ================== IMPORTS ==================


# =========== VARIABLES : logging ===========
logger = logging.getLogger("pgvector_store")
# =========== VARIABLES : logging ===========


# =========== VARIABLES : batch sizes ===========
_INSERT_BATCH_SIZE = 50
_FETCH_BATCH_SIZE = 1000
# =========== VARIABLES : batch sizes ===========


# =========== CLASS : PgVectorStore ===========
class PgVectorStore:
    """
    Supabase pgvector knowledge store (white-label version).
    Wraps knowledge_documents + knowledge_chunks tables.
    All public methods are thread-safe (Supabase client is stateless).
    """

    def __init__(self, supabase_client):
        self._client = supabase_client
        self._enabled = supabase_client is not None

    def health_check(self) -> bool:
        if not self._enabled:
            return False
        try:
            self._client.table("knowledge_documents").select("id", count="exact").limit(1).execute()
            return True
        except Exception as exc:
            logger.warning(f"pgvector health check failed: {exc}")
            return False

    def get_chunk_count(self) -> int:
        if not self._enabled:
            return 0
        try:
            resp = self._client.table("knowledge_chunks").select("id", count="exact").execute()
            return int(resp.count or 0)
        except Exception as exc:
            logger.warning(f"pgvector get_chunk_count failed: {exc}")
            return 0

    def get_all_chunks_via_rpc(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        try:
            resp = self._client.rpc("get_all_active_chunks", {}).execute()
            rows = resp.data or []
            logger.info(f"✅ pgvector RPC: loaded {len(rows)} active chunks")
            return rows
        except Exception as exc:
            logger.warning(f"⚠️ pgvector RPC failed: {exc}; trying direct table query")
            return self._get_all_chunks_paginated()

    def _get_all_chunks_paginated(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        results = []
        start = 0
        try:
            while True:
                resp = (
                    self._client.table("knowledge_chunks")
                    .select("id, document_id, source_name, content, metadata_json, embedding")
                    .order("id")
                    .range(start, start + _FETCH_BATCH_SIZE - 1)
                    .execute()
                )
                rows = resp.data or []
                if not rows:
                    break
                results.extend(rows)
                if len(rows) < _FETCH_BATCH_SIZE:
                    break
                start += _FETCH_BATCH_SIZE
            logger.info(f"pgvector fallback paginated: loaded {len(results)} chunks")
            return results
        except Exception as exc:
            logger.warning(f"pgvector paginated fallback also failed: {exc}")
            return []

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        source_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        try:
            params = {
                "query_embedding": query_embedding,
                "match_count": top_k,
                "source_filter": source_filter,
            }
            resp = self._client.rpc("match_knowledge_chunks", params).execute()
            return resp.data or []
        except Exception as exc:
            logger.warning(f"⚠️ pgvector search failed: {exc}")
            return []

    def create_document(
        self,
        filename: str,
        source_name: str = "uploaded",
        uploaded_by: str = "admin",
        extra_meta: Optional[Dict] = None,
    ) -> Optional[int]:
        if not self._enabled:
            return None
        try:
            payload = {
                "filename": filename,
                "source_name": source_name,
                "uploaded_by": uploaded_by,
                "status": "processing",
                "metadata_json": extra_meta or {},
            }
            resp = self._client.table("knowledge_documents").insert(payload).execute()
            if resp.data:
                return resp.data[0]["id"]
        except Exception as exc:
            logger.warning(f"pgvector create_document failed: {exc}")
        return None

    def upsert_chunks(
        self,
        document_id: int,
        chunk_rows: List[Dict[str, Any]],
        source_name: str = "uploaded",
    ) -> int:
        if not self._enabled or not chunk_rows:
            return 0
        inserted = 0
        try:
            for batch_start in range(0, len(chunk_rows), _INSERT_BATCH_SIZE):
                batch = chunk_rows[batch_start: batch_start + _INSERT_BATCH_SIZE]
                payload = []
                for row in batch:
                    meta = dict(row.get("metadata") or {})
                    meta.setdefault("url", row.get("url", ""))
                    meta.setdefault("title", row.get("title", ""))
                    meta.setdefault("category", row.get("category", "uploaded"))
                    meta.setdefault("section_type", row.get("section_type", "chunk"))
                    payload.append({
                        "document_id": document_id,
                        "source_name": source_name,
                        "content": row["text"],
                        "metadata_json": meta,
                        "embedding": row["embedding"],
                    })
                resp = self._client.table("knowledge_chunks").insert(payload).execute()
                inserted += len(resp.data or [])

            try:
                self._client.rpc(
                    "update_knowledge_document_chunk_count",
                    {"p_doc_id": document_id}
                ).execute()
                self._client.table("knowledge_documents").update(
                    {"status": "active"}
                ).eq("id", document_id).execute()
            except Exception:
                pass

            logger.info(f"✅ pgvector: inserted {inserted} chunks for document_id={document_id}")
            return inserted

        except Exception as exc:
            logger.warning(f"⚠️ pgvector upsert_chunks failed for doc {document_id}: {exc}")
            return 0

    def delete_by_document_id(self, document_id: int) -> int:
        if not self._enabled:
            return 0
        try:
            self._client.table("knowledge_documents").update(
                {"status": "deleted"}
            ).eq("id", document_id).execute()
            logger.info(f"✅ pgvector: soft-deleted document_id={document_id}")
            return 1
        except Exception as exc:
            logger.warning(f"⚠️ pgvector delete_by_document_id failed: {exc}")
            return 0

    def hard_delete_by_document_id(self, document_id: int) -> int:
        if not self._enabled:
            return 0
        try:
            self._client.table("knowledge_documents").delete().eq(
                "id", document_id
            ).execute()
            logger.info(f"✅ pgvector: hard-deleted document_id={document_id}")
            return 1
        except Exception as exc:
            logger.warning(f"⚠️ pgvector hard_delete_by_document_id failed: {exc}")
            return 0

    def create_base_knowledge_document(self) -> Optional[int]:
        if not self._enabled:
            return None
        try:
            resp = (
                self._client.table("knowledge_documents")
                .select("id")
                .eq("source_name", "base_knowledge")
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            if resp.data:
                return resp.data[0]["id"]
            resp = self._client.table("knowledge_documents").insert({
                "filename": "base_knowledge_batch",
                "source_name": "base_knowledge",
                "uploaded_by": "system",
                "status": "active",
            }).execute()
            if resp.data:
                return resp.data[0]["id"]
        except Exception as exc:
            logger.warning(f"pgvector create_base_knowledge_document failed: {exc}")
        return None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @staticmethod
    def row_to_doc(row: Dict[str, Any]) -> Dict[str, Any]:
        meta = row.get("metadata_json") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        return {
            "text": row.get("content", ""),
            "url": meta.get("url", ""),
            "title": meta.get("title", ""),
            "category": meta.get("category", row.get("source_name", "general")),
            "section_type": meta.get("section_type", "chunk"),
            "department": meta.get("department", "general"),
        }

# =========== CLASS : PgVectorStore ===========
