"""Extract plain text from PDF, DOCX, or TXT files."""

import io
import logging

import pdfplumber

log = logging.getLogger(__name__)


def extract_text(raw_bytes: bytes, filename: str) -> str:
    """Convert raw file bytes to plain text based on file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        return _extract_pdf(raw_bytes)
    elif ext == "docx":
        return _extract_docx(raw_bytes)
    elif ext == "txt":
        return raw_bytes.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: .{ext}")


def _extract_pdf(raw_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
    full = "\n\n".join(pages)
    log.info("Extracted %d chars from PDF (%d pages)", len(full), len(pages))
    return full


def _extract_docx(raw_bytes: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    from docx import Document

    doc = Document(io.BytesIO(raw_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full = "\n\n".join(paragraphs)
    log.info("Extracted %d chars from DOCX (%d paragraphs)", len(full), len(paragraphs))
    return full
