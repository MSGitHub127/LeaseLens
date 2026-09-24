"""
Turn an uploaded file's raw bytes into clean plain text. Kept separate from
validation (security.py) and interpretation (classification.py, rubric.py) so
each module has exactly one job and is easy to unit test in isolation.
"""
from __future__ import annotations

import io
import re


class ParsingError(ValueError):
    """Raised when a validated file still can't be turned into usable text."""


def parse_document(filename: str, content: bytes) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    try:
        if ext == ".pdf":
            text = _parse_pdf(content)
        elif ext == ".docx":
            text = _parse_docx(content)
        elif ext == ".txt":
            text = content.decode("utf-8", errors="replace")
        elif ext in (".png", ".jpg", ".jpeg", ".webp"):
            text = _parse_image(content, ext)
        else:
            raise ParsingError(f"No parser registered for '{ext}'.")
    except ParsingError:
        raise
    except Exception as exc:  # noqa: BLE001 - convert any parser failure into a clean error
        raise ParsingError(f"Could not read this {ext} file. It may be corrupted or password-protected.") from exc

    text = _normalize_whitespace(text)
    if len(text.strip()) < 20:
        raise ParsingError(
            "This document doesn't contain enough extractable text to analyze "
            "(it may be a blank or unreadable scan)."
        )
    return text


def _parse_image(content: bytes, ext: str) -> str:
    from PIL import Image

    from app.llm import get_llm_provider

    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception as exc:
        raise ParsingError("Invalid or corrupted image format.") from exc

    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "image/jpeg")
    provider = get_llm_provider()
    return provider.extract_text_from_image(content, mime_type)


def _parse_pdf(content: bytes) -> str:
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    text = "\n".join(pages).strip()

    # Fallback for scanned PDFs without a digital text layer:
    if len(text) < 40:
        try:
            import pypdfium2 as pdfium

            from app.llm import get_llm_provider

            pdf = pdfium.PdfDocument(io.BytesIO(content))
            page_texts = []
            provider = get_llm_provider()
            for i in range(min(len(pdf), 5)):
                page = pdf[i]
                pil_image = page.render(scale=2).to_pil()
                img_byte_arr = io.BytesIO()
                pil_image.save(img_byte_arr, format="JPEG", quality=85)
                img_bytes = img_byte_arr.getvalue()
                transcribed = provider.extract_text_from_image(img_bytes, "image/jpeg")
                if transcribed:
                    page_texts.append(transcribed)
            if page_texts:
                text = "\n\n".join(page_texts)
        except Exception:
            pass

    return text


def _parse_docx(content: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(content))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 800, overlap: int = 120) -> list[str]:
    """Split into overlapping chunks for retrieval (app/rag.py).

    Splitting on paragraph boundaries first keeps clauses intact more often
    than a naive fixed-width split, which matters for citation accuracy.
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= max_chars:
            current = f"{current}\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chars:
                # very long paragraph: hard-split with overlap
                start = 0
                while start < len(para):
                    end = start + max_chars
                    chunks.append(para[start:end])
                    start = end - overlap
                current = ""
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks
