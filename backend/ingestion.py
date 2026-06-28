# WHAT DOES THIS FILE DO: validate uploaded files, extract text from various formats, chunk it, and wrap chunks for RAG ingestion (white-label version)

# ================== IMPORTS ==================
import csv
import io
import json
import os
from typing import Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
    HAS_PDF = True
except Exception:
    HAS_PDF = False

try:
    from docx import Document as DocxDocument
    HAS_DOCX = True
except Exception:
    HAS_DOCX = False

try:
    from pptx import Presentation
    HAS_PPTX = True
except Exception:
    HAS_PPTX = False

try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except Exception:
    HAS_OCR = False

import os as _os_ing
# ================== IMPORTS ==================


# =========== VARIABLES : feature flags and upload config ===========
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv",
    ".pdf", ".doc", ".docx",
    ".ppt", ".pptx",
    ".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp",
}

_SIDECAR_DIR = _os_ing.path.join(_os_ing.path.dirname(_os_ing.path.abspath(__file__)), 'uploads', 'extracted_texts')
# =========== VARIABLES : feature flags and upload config ===========


def extension_of(filename: str) -> str:
    if not filename:
        return ""
    _, ext = os.path.splitext(filename.lower())
    return ext


def validate_upload(filename: str, file_size_bytes: int, max_size_bytes: int) -> None:
    ext = extension_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext or 'unknown'}")
    if file_size_bytes <= 0:
        raise ValueError("Uploaded file is empty")
    if file_size_bytes > max_size_bytes:
        raise ValueError(f"File too large: {file_size_bytes} bytes (max {max_size_bytes})")


def extract_text_from_bytes(filename: str, data: bytes) -> Tuple[str, Dict[str, str]]:
    ext = extension_of(filename)
    metadata = {"extension": ext}

    if ext in {".txt", ".md"}:
        return data.decode("utf-8", errors="ignore"), metadata

    if ext == ".json":
        parsed = json.loads(data.decode("utf-8", errors="ignore"))
        return json.dumps(parsed, ensure_ascii=False, indent=2), metadata

    if ext == ".csv":
        text = data.decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = []
        for row in reader:
            rows.append(" | ".join(cell.strip() for cell in row if cell is not None))
        return "\n".join(r for r in rows if r.strip()), metadata

    if ext == ".pdf":
        if not HAS_PDF:
            raise ValueError("PDF support unavailable. Install PyMuPDF.")
        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for idx, page in enumerate(doc, start=1):
            text = page.get_text("text")
            if text and text.strip():
                pages.append(f"[Page {idx}]\n{text.strip()}")
        doc.close()
        return "\n\n".join(pages), metadata

    if ext == ".docx":
        if not HAS_DOCX:
            raise ValueError("DOCX support unavailable. Install python-docx.")
        document = DocxDocument(io.BytesIO(data))
        parts = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]
        return "\n".join(parts), metadata

    if ext == ".doc":
        raise ValueError("Legacy .doc files are not directly supported. Please convert to .docx and upload again.")

    if ext == ".pptx":
        if not HAS_PPTX:
            raise ValueError("PPTX support unavailable. Install python-pptx.")
        presentation = Presentation(io.BytesIO(data))
        slides = []
        for idx, slide in enumerate(presentation.slides, start=1):
            texts = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    val = shape.text.strip()
                    if val:
                        texts.append(val)
            if texts:
                slides.append(f"[Slide {idx}]\n" + "\n".join(texts))
        return "\n\n".join(slides), metadata

    if ext == ".ppt":
        raise ValueError("Legacy .ppt files are not directly supported. Please convert to .pptx and upload again.")

    if ext in {".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"}:
        if not HAS_OCR:
            raise ValueError("OCR support unavailable. Install pillow + pytesseract and configure Tesseract binary.")
        image = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(image)
        return text.strip(), metadata

    raise ValueError(f"Unsupported file type: {ext or 'unknown'}")


def chunk_text(text: str, max_chars: int = 1500, overlap: int = 200) -> List[str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: List[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + max_chars, len(cleaned))
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def build_upload_chunks(
    *,
    filename: str,
    display_title: Optional[str],
    extracted_text: str,
    url_hint: str = "",
    category: str = "uploaded",
) -> List[Dict[str, str]]:
    title = (display_title or filename or "Uploaded Knowledge").strip()
    blocks = chunk_text(extracted_text, max_chars=1500, overlap=200)
    chunks: List[Dict[str, str]] = []
    for idx, block in enumerate(blocks):
        chunks.append(
            {
                "title": title,
                "text": block,
                "url": url_hint,
                "category": category,
                "section_type": f"upload_chunk_{idx + 1}",
                "metadata": {
                    "filename": filename,
                    "chunk_index": idx,
                },
            }
        )
    return chunks


def save_extracted_text(upload_id, text):
    try:
        _os_ing.makedirs(_SIDECAR_DIR, exist_ok=True)
        path = _os_ing.path.join(_SIDECAR_DIR, 'upload_' + str(upload_id) + '_extracted.txt')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path
    except Exception:
        return None


def load_extracted_text(path):
    if not path or not _os_ing.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return fh.read()
    except Exception:
        return None
