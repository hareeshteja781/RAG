from typing import Any, Dict, List
import heapq
import math


def _cosine(a, b):
    if not a or not b:
        return -1.0

    if len(a) != len(b):
        return -1.0

    dot = sum(x * y for x, y in zip(a, b))

    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return -1.0

    return dot / (norm_a * norm_b)


def search_similar_chunks(
    query_embedding,
    chunks: List[Dict[str, Any]],
    top_k: int = 5,
):
    if not chunks or top_k <= 0:
        return []

    heap = []

    for chunk in chunks:
        embedding = chunk.get("embedding")

        if not embedding:
            continue

        score = _cosine(
            query_embedding,
            embedding,
        )

        if score < 0:
            continue

        chunk_id = chunk.get("id", 0)

        # Include chunk_id as a tie-breaker so heapq
        # never tries to compare dictionaries.
        item = (score, chunk_id, chunk)

        if len(heap) < top_k:
            heapq.heappush(heap, item)

        elif score > heap[0][0]:
            heapq.heapreplace(heap, item)

    results = [
        heapq.heappop(heap)
        for _ in range(len(heap))
    ]

    results.reverse()

    return [
        {
            "score": score,
            **chunk,
        }
        for score, _, chunk in results
    ]