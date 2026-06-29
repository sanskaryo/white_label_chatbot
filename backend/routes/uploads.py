# WHAT DOES THIS FILE DO: Document upload and management endpoints

# ================== IMPORTS ==================
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form

from config import AZURE_EMBEDDING_MODEL, UPLOAD_MAX_FILE_SIZE_BYTES, PGVECTOR_ENABLED
from core.dependencies import get_service
from ingestion import validate_upload, extract_text_from_bytes, build_upload_chunks
from workflow_db import (
    create_upload_document, get_upload_document, list_upload_documents,
    delete_upload_document, mark_upload_failed, save_upload_chunks
)

try:
    from pgvector_store import pgvector_store
except Exception:
    pgvector_store = None
# ================== IMPORTS ==================

logger = logging.getLogger("white_label")
router = APIRouter()


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
):
    service = get_service()

    filename = file.filename or "unknown"
    data = await file.read()
    file_size = len(data)

    try:
        validate_upload(filename, file_size, UPLOAD_MAX_FILE_SIZE_BYTES)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    doc_record = create_upload_document(filename=filename, content_type=file.content_type or "", file_size_bytes=file_size)
    upload_id = doc_record["id"]

    async def _process():
        try:
            extracted_text, _meta = extract_text_from_bytes(filename, data)
            if not extracted_text.strip():
                mark_upload_failed(upload_id, "No text content could be extracted")
                return

            chunks = build_upload_chunks(
                filename=filename,
                display_title=title or filename,
                extracted_text=extracted_text,
                url_hint=f"upload://{upload_id}/",
                category="uploaded",
            )

            embedded_chunks = []
            batch_size = 10
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i: i + batch_size]
                texts = [c["text"] for c in batch]
                resp = service.azure_client.embeddings.create(input=texts, model=AZURE_EMBEDDING_MODEL)
                for chunk, emb_item in zip(batch, resp.data):
                    chunk["embedding"] = emb_item.embedding
                    embedded_chunks.append(chunk)

            save_upload_chunks(upload_id, embedded_chunks)

            if PGVECTOR_ENABLED and pgvector_store:
                pgv_doc_id = pgvector_store.create_document(filename=filename, source_name="uploaded", uploaded_by="admin")
                if pgv_doc_id:
                    pgvector_store.upsert_chunks(pgv_doc_id, [
                        {
                            "text": c["text"], "embedding": c["embedding"],
                            "url": c.get("url", ""), "title": c.get("title", ""),
                            "category": c.get("category", "uploaded")
                        }
                        for c in embedded_chunks
                    ])

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
    return {"upload_id": upload_id, "filename": filename, "status": "processing"}


@router.get("/uploads")
def list_uploads_endpoint(limit: int = 100):
    return {"items": list_upload_documents(limit=limit)}


@router.delete("/uploads/{upload_id}")
def delete_upload_endpoint(upload_id: int):
    service = get_service()

    doc = get_upload_document(upload_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    delete_upload_document(upload_id)
    service.remove_upload_from_index(upload_id)

    if PGVECTOR_ENABLED and pgvector_store and doc.get("pgvector_document_id"):
        pgvector_store.delete_by_document_id(doc["pgvector_document_id"])

    return {"deleted": True}
