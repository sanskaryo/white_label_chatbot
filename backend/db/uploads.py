# WHAT DOES THIS FILE DO: upload document and chunk CRUD — create, list, delete, and S3 key tracking

# ================== IMPORTS ==================
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from .connection import session_scope
from .models import UploadDocument, UploadChunk
# ================== IMPORTS ==================


# =========== FUNCTION ===========
# ROLE: Create a new upload document record in processing state
def create_upload_document(filename: str, content_type: str = "", file_size_bytes: int = 0, uploader_id: str = "admin") -> Dict[str, Any]:
    ''' Insert upload record and return its ID, filename, and status '''

    # FLOW-1: Insert document in processing state
    with session_scope() as session:
        row = UploadDocument(
            filename=filename, content_type=content_type,
            file_size_bytes=file_size_bytes, uploader_id=uploader_id,
            status="processing", is_active=True,
        )
        session.add(row)

        # FLOW-2: Flush to get DB-assigned ID
        session.flush()
        return {"id": row.id, "filename": row.filename, "status": row.status}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Save extracted and embedded chunks for an upload document
def save_upload_chunks(upload_id: int, chunks: List[Dict[str, Any]]) -> int:
    ''' Insert chunk rows and update parent document to processed; return count saved '''

    # FLOW-1: Load parent document first
    with session_scope() as session:
        doc = session.get(UploadDocument, upload_id)
        if not doc:
            return 0

        # FLOW-2: Insert each chunk row
        count = 0
        for idx, chunk in enumerate(chunks):
            row = UploadChunk(
                upload_id=upload_id, chunk_index=idx,
                title=chunk.get("title", ""), text=chunk["text"],
                source_url=chunk.get("url", ""), category=chunk.get("category", "uploaded"),
                section_type=chunk.get("section_type", "uploaded_chunk"),
                embedding_json=chunk.get("embedding", []),
                is_active=True,
            )
            session.add(row)
            count += 1

        # FLOW-3: Update document status now that chunks are saved
        doc.total_chunks = count
        doc.status = "processed"
        doc.processed_at = datetime.now(timezone.utc)

        return count
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Mark an upload as failed with the error reason
def mark_upload_failed(upload_id: int, error_message: str) -> None:
    ''' Set upload status to failed and store the error message '''

    # FLOW-1: Load and update status
    with session_scope() as session:
        doc = session.get(UploadDocument, upload_id)
        if doc:
            doc.status = "failed"
            doc.error_message = error_message
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: List all active upload documents for the admin panel
def list_upload_documents(limit: int = 100) -> List[Dict[str, Any]]:
    ''' Return active upload records ordered newest first '''

    # FLOW-1: Query active uploads
    with session_scope() as session:
        rows = session.execute(
            select(UploadDocument).where(UploadDocument.is_active.is_(True)).order_by(UploadDocument.created_at.desc()).limit(limit)
        ).scalars().all()

        # FLOW-2: Return as dicts with ISO timestamp
        return [
            {"id": r.id, "filename": r.filename, "display_title": r.display_title,
             "status": r.status, "total_chunks": r.total_chunks,
             "file_size_bytes": r.file_size_bytes, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Soft-delete an upload document by marking it inactive
def delete_upload_document(upload_id: int) -> bool:
    ''' Mark upload as inactive; return True if found, False if not '''

    # FLOW-1: Load and mark inactive
    with session_scope() as session:
        doc = session.get(UploadDocument, upload_id)
        if doc:
            doc.is_active = False
            return True

    return False
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Retrieve a single upload document by ID
def get_upload_document(upload_id: int) -> Optional[Dict[str, Any]]:
    ''' Return upload document dict, or None if not found '''

    # FLOW-1: Load by primary key
    with session_scope() as session:
        doc = session.get(UploadDocument, upload_id)
        if not doc:
            return None

        # FLOW-2: Return the fields needed by routes
        return {
            "id": doc.id, "filename": doc.filename, "status": doc.status,
            "total_chunks": doc.total_chunks, "pgvector_document_id": doc.pgvector_document_id,
            "s3_key": doc.s3_key,
        }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Load all active upload chunks with their embeddings for RAG indexing
def get_active_upload_chunks(limit: int = 50000) -> List[Dict[str, Any]]:
    ''' Return active chunk records with embedding vectors for runtime index hydration '''

    # FLOW-1: Query active chunks up to limit
    with session_scope() as session:
        rows = session.execute(
            select(UploadChunk).where(UploadChunk.is_active.is_(True)).limit(limit)
        ).scalars().all()

        # FLOW-2: Return as dicts with embedding field
        return [
            {"text": r.text, "url": r.source_url, "title": r.title,
             "category": r.category, "section_type": r.section_type, "embedding": r.embedding_json}
            for r in rows
        ]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Store the S3 key on an upload document after the file is saved to S3
def update_upload_s3_key(upload_id: int, s3_key: str) -> None:
    ''' Write the S3 file path to the upload document record '''

    # FLOW-1: Load and update s3_key field
    with session_scope() as session:
        doc = session.get(UploadDocument, upload_id)
        if doc:
            doc.s3_key = s3_key
# =========== FUNCTION ===========
