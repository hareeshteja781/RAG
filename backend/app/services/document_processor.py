import os
from datetime import datetime
from typing import Optional

from pypdf import PdfReader
import docx


def extract_text(file_path: str, file_type: Optional[str] = None) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    if ext == ".pdf":
        try:
            reader = PdfReader(file_path)
            pages = []
            for p in reader.pages:
                pages.append(p.extract_text() or "")
            text = "\n\n".join(pages)
        except Exception:
            raise
    elif ext == ".docx":
        try:
            doc = docx.Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text]
            text = "\n\n".join(paragraphs)
        except Exception:
            raise
    elif ext == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1") as f:
                text = f.read()
    else:
        raise ValueError("Unsupported file type for extraction")

    return text
