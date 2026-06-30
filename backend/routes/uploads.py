# WHAT DOES THIS FILE DO: Document upload endpoints — saves files to Supabase S3 and processes them for RAG

# ================== IMPORTS ==================
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Request

from config import AZURE_EMBEDDING_MODEL, UPLOAD_MAX_FILE_SIZE_BYTES, PGVECTOR_ENABLED
from core.dependencies import get_service
from ingestion import validate_upload, extract_text_from_bytes, build_upload_chunks
from workflow_db import (
    create_upload_document, get_upload_document, list_upload_documents,
    delete_upload_document, mark_upload_failed, save_upload_chunks, update_upload_s3_key
)

try:
    from pgvector_store import pgvector_store
except Exception:
    pgvector_store = None

try:
    from storage import supabase_storage
except Exception:
    supabase_storage = None
# ================== IMPORTS ==================


# =========== VARIABLES : logging ===========
logger = logging.getLogger("white_label")
# =========== VARIABLES : logging ===========


router = APIRouter()


# =========== FUNCTION ===========
# ROLE: Build the S3 key path for a given upload
def _build_s3_key(upload_id: int, filename: str) -> str:
    ''' Return s3 key like uploads/42/filename.pdf '''

    # FLOW-1: Combine upload_id and filename into a path
    safe_name = filename.replace(" ", "_")
    return f"uploads/{upload_id}/{safe_name}"
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Upload a document file, store to S3, and process chunks in background
@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
):
    ''' Accept file upload, save to S3, and trigger background processing '''

    # FLOW-1: Read file bytes and validate type/size
    service = get_service()
    filename = file.filename or "unknown"
    data = await file.read()
    file_size = len(data)

    try:
        validate_upload(filename, file_size, UPLOAD_MAX_FILE_SIZE_BYTES)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # FLOW-2: Create DB record so we get an upload_id to use in S3 key
    uploader_id = request.headers.get("X-User-Email", "admin")
    doc_record = create_upload_document(
        filename=filename,
        content_type=file.content_type or "",
        file_size_bytes=file_size,
        uploader_id=uploader_id,
    )
    upload_id = doc_record["id"]

    # FLOW-3: Upload raw file to S3 if storage is available
    s3_key = _build_s3_key(upload_id, filename)
    if supabase_storage and supabase_storage.enabled:
        uploaded = supabase_storage.upload_file(s3_key, data, content_type=file.content_type or "application/octet-stream")
        if uploaded:
            update_upload_s3_key(upload_id, s3_key)
        else:
            logger.warning(f"S3 upload failed for {filename}, processing from memory")

    # FLOW-4: Start background task to extract, chunk, embed, and index
    async def _process():
        try:
            extracted_text, _meta = extract_text_from_bytes(filename, data)
            if not extracted_text.strip():
                mark_upload_failed(upload_id, "No text content could be extracted")
                return

            # FLOW-5: Build chunks from extracted text
            chunks = build_upload_chunks(
                filename=filename,
                display_title=title or filename,
                extracted_text=extracted_text,
                url_hint=f"upload://{upload_id}/",
                category="uploaded",
            )

            # FLOW-6: Embed each chunk using Azure OpenAI in batches
            embedded_chunks = []
            batch_size = 10
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i: i + batch_size]
                texts = [c["text"] for c in batch]
                resp = service.azure_client.embeddings.create(input=texts, model=AZURE_EMBEDDING_MODEL)
                for chunk, emb_item in zip(batch, resp.data):
                    chunk["embedding"] = emb_item.embedding
                    embedded_chunks.append(chunk)

            # FLOW-7: Save chunks to workflow DB
            save_upload_chunks(upload_id, embedded_chunks)

            # FLOW-8: Also store in pgvector for persistent vector search
            if PGVECTOR_ENABLED and pgvector_store:
                pgv_doc_id = pgvector_store.create_document(filename=filename, source_name="uploaded", uploaded_by=uploader_id)
                if pgv_doc_id:
                    pgvector_store.upsert_chunks(pgv_doc_id, [
                        {
                            "text": c["text"], "embedding": c["embedding"],
                            "url": c.get("url", ""), "title": c.get("title", ""),
                            "category": c.get("category", "uploaded")
                        }
                        for c in embedded_chunks
                    ])

            # FLOW-9: Add to in-memory RAG index for immediate search availability
            docs = [
                {
                    "text": c["text"], "url": c.get("url", ""),
                    "title": c.get("title", ""), "category": c.get("category", "uploaded"),
                    "section_type": c.get("section_type", "")
                }
                for c in embedded_chunks
            ]
            embeddings = [c["embedding"] for c in embedded_chunks]
            service.extend_runtime_index(docs, embeddings)

            logger.info(f"Upload {upload_id} processed: {len(embedded_chunks)} chunks")

        except Exception as exc:
            logger.exception(f"Upload {upload_id} failed: {exc}")
            mark_upload_failed(upload_id, str(exc))

    background_tasks.add_task(_process)
    return {"upload_id": upload_id, "filename": filename, "status": "processing", "s3_key": s3_key}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: List all uploaded documents
@router.get("/uploads")
def list_uploads_endpoint(limit: int = 100):
    ''' Return list of uploaded documents with their processing status '''
    return {"items": list_upload_documents(limit=limit)}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Get signed download URL for an uploaded file from S3
@router.get("/uploads/{upload_id}/download-url")
def get_upload_download_url(upload_id: int):
    ''' Return a signed S3 URL for downloading the original file '''

    # FLOW-1: Load upload record and check it exists
    doc = get_upload_document(upload_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    # FLOW-2: Return error if file not in S3
    s3_key = doc.get("s3_key")
    if not s3_key or not supabase_storage or not supabase_storage.enabled:
        raise HTTPException(status_code=404, detail="File not available in storage")

    # FLOW-3: Generate and return signed URL valid for 1 hour
    url = supabase_storage.get_signed_url(s3_key, expires_in=3600)
    if not url:
        raise HTTPException(status_code=500, detail="Could not generate download URL")

    return {"url": url, "expires_in": 3600}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Delete an upload document from DB, S3, and search index
@router.delete("/uploads/{upload_id}")
def delete_upload_endpoint(upload_id: int):
    ''' Remove upload record, S3 file, and index entries '''

    # FLOW-1: Load upload record and check it exists
    service = get_service()
    doc = get_upload_document(upload_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    # FLOW-2: Soft delete from workflow DB
    delete_upload_document(upload_id)

    # FLOW-3: Remove from in-memory RAG index
    service.remove_upload_from_index(upload_id)

    # FLOW-4: Delete from pgvector if it was stored there
    if PGVECTOR_ENABLED and pgvector_store and doc.get("pgvector_document_id"):
        pgvector_store.delete_by_document_id(doc["pgvector_document_id"])

    # FLOW-5: Delete raw file from S3 bucket
    s3_key = doc.get("s3_key")
    if s3_key and supabase_storage and supabase_storage.enabled:
        supabase_storage.delete_file(s3_key)

    return {"deleted": True}
# =========== FUNCTION ===========
