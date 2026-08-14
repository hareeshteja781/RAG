from typing import Any, Dict, List


def assemble_context(
    chunks: List[Dict[str, Any]],
    max_chars: int = 6000,
) -> str:

    parts = []
    total = 0

    for index, chunk in enumerate(chunks, start=1):
        text = (chunk.get("content") or "").strip()

        if not text:
            continue

        filename = chunk.get("filename") or "Unknown document"

        section = (
            f"[Source {index}: {filename}]\n"
            f"{text}"
        )

        if total + len(section) > max_chars:
            remaining = max_chars - total

            if remaining > 0:
                parts.append(section[:remaining])

            break

        parts.append(section)
        total += len(section)

    return "\n\n".join(parts)