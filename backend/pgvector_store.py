# WHAT DOES THIS FILE DO: Supabase pgvector wrapper for storing and searching knowledge chunks

# ================== IMPORTS ==================
import logging
import json
from typing import Any, Dict, List, Optional
# ================== IMPORTS ==================


# =========== VARIABLES : logging ===========
logger = logging.getLogger("pgvector_store")
# =========== VARIABLES : logging ===========


# =========== VARIABLES : batch configuration ===========
_INSERT_BATCH_SIZE = 50
_FETCH_BATCH_SIZE = 1000
# =========== VARIABLES : batch configuration ===========


# =========== CLASS ===========

class PgVectorStore:
    '''Thread-safe wrapper around Supabase pgvector for document storage and retrieval'''

    # =========== FUNCTION ===========
    def __init__(self, supabase_client):
        ''' Initialize with a Supabase client instance '''

        # FLOW-1: Store client and track if it's available
        self._client = supabase_client
        self._enabled = supabase_client is not None
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Check if Supabase connection is healthy
    def health_check(self) -> bool:
        ''' Return True if pgvector is reachable, False otherwise '''

        # FLOW-1: Skip check if pgvector not enabled
        if not self._enabled:
            return False

        # FLOW-2: Try a simple query to validate connection
        try:
            self._client.table("knowledge_documents").select("id", count="exact").limit(1).execute()
            return True

        except Exception as exc:
            logger.warning(f"pgvector health check failed: {exc}")
            return False
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Get total count of all chunks in pgvector
    def get_chunk_count(self) -> int:
        ''' Return the total number of stored chunks, or 0 if unavailable '''

        # FLOW-1: Return 0 if pgvector not enabled
        if not self._enabled:
            return 0

        # FLOW-2: Query chunk table for total count
        try:
            resp = self._client.table("knowledge_chunks").select("id", count="exact").execute()
            return int(resp.count or 0)

        except Exception as exc:
            logger.warning(f"pgvector get_chunk_count failed: {exc}")
            return 0
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Load all active chunks from pgvector via RPC call
    def get_all_chunks_via_rpc(self) -> List[Dict[str, Any]]:
        ''' Fetch all active chunks using RPC, fall back to paginated query if needed '''

        # FLOW-1: Return empty if pgvector not enabled
        if not self._enabled:
            return []

        # FLOW-2: Try RPC call for efficient bulk fetch
        try:
            resp = self._client.rpc("get_all_active_chunks", {}).execute()
            rows = resp.data or []
            logger.info(f"pgvector RPC: loaded {len(rows)} active chunks")
            return rows

        except Exception as exc:
            logger.warning(f"pgvector RPC failed: {exc}; trying paginated fallback")
            return self._get_all_chunks_paginated()
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Paginated fallback to fetch all chunks when RPC unavailable
    def _get_all_chunks_paginated(self) -> List[Dict[str, Any]]:
        ''' Fetch chunks in batches if RPC method not available '''

        # FLOW-1: Return empty if pgvector not enabled
        if not self._enabled:
            return []

        # FLOW-2: Initialize accumulator and offset for pagination
        results = []
        start = 0

        # FLOW-3: Loop through batches until all chunks fetched
        try:
            while True:
                resp = (
                    self._client.table("knowledge_chunks")
                    .select("id, document_id, source_name, content, metadata_json, embedding")
                    .order("id")
                    .range(start, start + _FETCH_BATCH_SIZE - 1)
                    .execute()
                )

                # FLOW-4: Check if current batch has rows
                rows = resp.data or []
                if not rows:
                    break

                # FLOW-5: Accumulate rows and advance offset
                results.extend(rows)
                if len(rows) < _FETCH_BATCH_SIZE:
                    break

                start += _FETCH_BATCH_SIZE

            logger.info(f"pgvector paginated: loaded {len(results)} chunks")
            return results

        except Exception as exc:
            logger.warning(f"pgvector paginated fallback failed: {exc}")
            return []
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Search pgvector for similar chunks using query embedding
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        source_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ''' Retrieve top-k chunks most similar to the query embedding '''

        # FLOW-1: Return empty if pgvector not enabled
        if not self._enabled:
            return []

        # FLOW-2: Call RPC search function with embedding and filters
        try:
            params = {
                "query_embedding": query_embedding,
                "match_count": top_k,
                "source_filter": source_filter,
            }
            resp = self._client.rpc("match_knowledge_chunks", params).execute()
            return resp.data or []

        except Exception as exc:
            logger.warning(f"pgvector search failed: {exc}")
            return []
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Create a new document record in pgvector
    def create_document(
        self,
        filename: str,
        source_name: str = "uploaded",
        uploaded_by: str = "admin",
        extra_meta: Optional[Dict] = None,
    ) -> Optional[int]:
        ''' Insert new document and return its ID, or None if failed '''

        # FLOW-1: Return None if pgvector not enabled
        if not self._enabled:
            return None

        # FLOW-2: Prepare document payload
        try:
            payload = {
                "filename": filename,
                "source_name": source_name,
                "uploaded_by": uploaded_by,
                "status": "processing",
                "metadata_json": extra_meta or {},
            }

            # FLOW-3: Insert and extract ID from response
            resp = self._client.table("knowledge_documents").insert(payload).execute()
            if resp.data:
                return resp.data[0]["id"]

        except Exception as exc:
            logger.warning(f"pgvector create_document failed: {exc}")

        return None
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Insert chunks for a document and update its status
    def upsert_chunks(
        self,
        document_id: int,
        chunk_rows: List[Dict[str, Any]],
        source_name: str = "uploaded",
    ) -> int:
        ''' Batch insert chunks and mark document as active; return count inserted '''

        # FLOW-1: Return 0 if pgvector disabled or no chunks provided
        if not self._enabled or not chunk_rows:
            return 0

        # FLOW-2: Initialize inserted counter
        inserted = 0

        # FLOW-3: Process chunks in batches
        try:
            for batch_start in range(0, len(chunk_rows), _INSERT_BATCH_SIZE):
                batch = chunk_rows[batch_start: batch_start + _INSERT_BATCH_SIZE]
                payload = []

                # FLOW-4: Transform each chunk to pgvector schema
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

                # FLOW-5: Insert batch and count results
                resp = self._client.table("knowledge_chunks").insert(payload).execute()
                inserted += len(resp.data or [])

            # FLOW-6: Update document status to active
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

            logger.info(f"pgvector: inserted {inserted} chunks for document_id={document_id}")
            return inserted

        except Exception as exc:
            logger.warning(f"pgvector upsert_chunks failed for doc {document_id}: {exc}")
            return 0
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Soft-delete a document by marking it as deleted
    def delete_by_document_id(self, document_id: int) -> int:
        ''' Mark document as deleted (soft delete); return 1 if success, 0 if failed '''

        # FLOW-1: Return 0 if pgvector not enabled
        if not self._enabled:
            return 0

        # FLOW-2: Update document status to deleted
        try:
            self._client.table("knowledge_documents").update(
                {"status": "deleted"}
            ).eq("id", document_id).execute()
            logger.info(f"pgvector: soft-deleted document_id={document_id}")
            return 1

        except Exception as exc:
            logger.warning(f"pgvector delete_by_document_id failed: {exc}")
            return 0
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Permanently remove a document and its chunks from pgvector
    def hard_delete_by_document_id(self, document_id: int) -> int:
        ''' Delete document record permanently; return 1 if success, 0 if failed '''

        # FLOW-1: Return 0 if pgvector not enabled
        if not self._enabled:
            return 0

        # FLOW-2: Delete document record entirely
        try:
            self._client.table("knowledge_documents").delete().eq(
                "id", document_id
            ).execute()
            logger.info(f"pgvector: hard-deleted document_id={document_id}")
            return 1

        except Exception as exc:
            logger.warning(f"pgvector hard_delete_by_document_id failed: {exc}")
            return 0
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    # ROLE: Get or create the base knowledge document
    def create_base_knowledge_document(self) -> Optional[int]:
        ''' Return existing base knowledge doc ID, or create and return new ID '''

        # FLOW-1: Return None if pgvector not enabled
        if not self._enabled:
            return None

        # FLOW-2: Try to find existing base knowledge document
        try:
            resp = (
                self._client.table("knowledge_documents")
                .select("id")
                .eq("source_name", "base_knowledge")
                .eq("status", "active")
                .limit(1)
                .execute()
            )

            # FLOW-3: Return ID if document already exists
            if resp.data:
                return resp.data[0]["id"]

            # FLOW-4: Create new base knowledge document if not found
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
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    @property
    def enabled(self) -> bool:
        ''' Check if pgvector is enabled '''
        return self._enabled
    # =========== FUNCTION ===========


    # =========== FUNCTION ===========
    @staticmethod
    def row_to_doc(row: Dict[str, Any]) -> Dict[str, Any]:
        ''' Transform a pgvector row into document format for RAG service '''

        # FLOW-1: Extract and parse metadata JSON
        meta = row.get("metadata_json") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        # FLOW-2: Map pgvector row to document schema
        return {
            "text": row.get("content", ""),
            "url": meta.get("url", ""),
            "title": meta.get("title", ""),
            "category": meta.get("category", row.get("source_name", "general")),
            "section_type": meta.get("section_type", "chunk"),
            "department": meta.get("department", "general"),
        }
    # =========== FUNCTION ===========

# =========== CLASS ===========
