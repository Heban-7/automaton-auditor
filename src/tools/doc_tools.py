"""Forensic tools for the DocAnalyst (Paperwork Detective) and VisionInspector.

Uses the docling library for PDF parsing with a fallback to PyMuPDF.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# PDF ingestion
# ---------------------------------------------------------------------------


def ingest_pdf(pdf_path: str) -> list[dict[str, Any]]:
    """Parse *pdf_path* and return a list of text chunks.

    Each chunk is ``{"page": int, "text": str}``.  Tries docling first,
    then falls back to PyMuPDF (fitz).
    """
    chunks = _try_docling(pdf_path)
    if chunks is not None:
        return chunks

    chunks = _try_pymupdf(pdf_path)
    if chunks is not None:
        return chunks

    raise RuntimeError(
        f"Could not parse PDF at {pdf_path}. "
        "Install docling or PyMuPDF (pip install pymupdf)."
    )


def _try_docling(pdf_path: str) -> list[dict[str, Any]] | None:
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        full_text = result.document.export_to_markdown()
        paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
        return [{"page": i // 5 + 1, "text": p} for i, p in enumerate(paragraphs)]
    except Exception:
        return None


def _try_pymupdf(pdf_path: str) -> list[dict[str, Any]] | None:
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        chunks: list[dict[str, Any]] = []
        for page_num, page in enumerate(doc, 1):
            text = page.get_text()
            if text.strip():
                chunks.append({"page": page_num, "text": text.strip()})
        doc.close()
        return chunks
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Chunked search (RAG-lite)
# ---------------------------------------------------------------------------


def search_pdf_chunks(
    chunks: list[dict[str, Any]], query: str, *, top_k: int = 5
) -> list[dict[str, Any]]:
    """Simple keyword search over PDF chunks.

    Returns the *top_k* chunks whose text contains the most query-word hits.
    """
    query_words = set(query.lower().split())
    scored: list[tuple[int, dict]] = []
    for chunk in chunks:
        text_lower = chunk["text"].lower()
        hits = sum(1 for w in query_words if w in text_lower)
        if hits > 0:
            scored.append((hits, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


def search_keywords(
    chunks: list[dict[str, Any]], keywords: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """For each keyword, return chunks that contain it and a context snippet."""
    results: dict[str, list[dict[str, Any]]] = {}
    for kw in keywords:
        kw_lower = kw.lower()
        matches: list[dict[str, Any]] = []
        for chunk in chunks:
            if kw_lower in chunk["text"].lower():
                idx = chunk["text"].lower().index(kw_lower)
                start = max(0, idx - 200)
                end = min(len(chunk["text"]), idx + len(kw) + 200)
                matches.append({
                    "page": chunk["page"],
                    "context": chunk["text"][start:end],
                })
        results[kw] = matches
    return results


# ---------------------------------------------------------------------------
# File-path extraction and cross-referencing
# ---------------------------------------------------------------------------

_FILE_PATH_RE = re.compile(
    r"""(?:^|[\s"'`(])"""            # boundary
    r"""((?:src|tests?|lib|app)"""    # common root dirs
    r"""(?:/[\w.\-]+)+"""            # path segments
    r"""\.(?:py|js|ts|json|yaml|yml|toml|md|txt))""",  # extension
    re.MULTILINE,
)


def extract_file_paths_from_text(text: str) -> list[str]:
    """Extract plausible source-file paths from free text."""
    return list(dict.fromkeys(_FILE_PATH_RE.findall(text)))


def extract_file_paths_from_chunks(
    chunks: list[dict[str, Any]],
) -> list[str]:
    """Extract all file paths mentioned across PDF chunks."""
    paths: list[str] = []
    for chunk in chunks:
        paths.extend(extract_file_paths_from_text(chunk["text"]))
    return list(dict.fromkeys(paths))


def cross_reference_paths(
    claimed_paths: list[str], existing_files: list[str]
) -> dict[str, list[str]]:
    """Compare *claimed_paths* (from the report) against *existing_files*.

    Returns ``{"verified": [...], "hallucinated": [...]}``.
    """
    existing_set = set(existing_files)
    normalised_existing = {p.replace("\\", "/") for p in existing_set}

    verified: list[str] = []
    hallucinated: list[str] = []
    for p in claimed_paths:
        normalised = p.replace("\\", "/")
        if normalised in normalised_existing:
            verified.append(p)
        else:
            hallucinated.append(p)
    return {"verified": verified, "hallucinated": hallucinated}


# ---------------------------------------------------------------------------
# Image extraction from PDF (for VisionInspector)
# ---------------------------------------------------------------------------


def extract_images_from_pdf(pdf_path: str) -> list[str]:
    """Extract images from a PDF and save them to a temp directory.

    Returns a list of saved image file paths.
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        tmp_dir = tempfile.mkdtemp(prefix="auditor_images_")
        saved: list[str] = []
        for page_num, page in enumerate(doc):
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                ext = base_image["ext"]
                img_bytes = base_image["image"]
                fname = f"page{page_num + 1}_img{img_index + 1}.{ext}"
                fpath = os.path.join(tmp_dir, fname)
                with open(fpath, "wb") as f:
                    f.write(img_bytes)
                saved.append(fpath)
        doc.close()
        return saved
    except Exception:
        return []
