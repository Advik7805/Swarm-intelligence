"""Seed ingestion: uploaded files + pasted text → one combined seed corpus."""
import io

import fitz  # PyMuPDF
from charset_normalizer import from_bytes


def _decode(data: bytes) -> str:
    match = from_bytes(data).best()
    return str(match) if match else data.decode("utf-8", errors="replace")


def extract_file(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        with fitz.open(stream=io.BytesIO(data), filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    if name.endswith((".txt", ".md", ".csv", ".log", ".json")):
        return _decode(data)
    # Unknown type: best-effort decode
    return _decode(data)


def chunks(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    text = " ".join(text.split())
    if len(text) <= size:
        return [text] if text else []
    out, i = [], 0
    while i < len(text):
        out.append(text[i: i + size])
        i += size - overlap
    return out


def combine(seed_text: str, files: list[tuple[str, bytes]]) -> str:
    parts = [seed_text.strip()] if seed_text.strip() else []
    for fname, data in files:
        extracted = extract_file(fname, data).strip()
        if extracted:
            parts.append(f"[{fname}]\n{extracted}")
    combined = "\n\n".join(parts)
    if not combined.strip():
        raise ValueError("Seed is empty — provide text or at least one readable file.")
    return combined
