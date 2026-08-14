import re
from typing import List


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    if not text:
        return []

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split(" ")

    chunks = []
    start = 0
    n = len(words)
    while start < n:
        end = min(n, start + chunk_size)
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap)

    return chunks
