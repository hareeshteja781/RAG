import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types


ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "gemini-embedding-2"
)

EMBEDDING_DIM = int(
    os.getenv("EMBEDDING_DIM", "1536")
)


if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured")


client = genai.Client(api_key=GEMINI_API_KEY)


def generate_embeddings(
    texts: List[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> List[Optional[List[float]]]:

    if not texts:
        return []

    results: List[Optional[List[float]]] = [None] * len(texts)

    valid_contents = []
    valid_indexes = []

    for index, text in enumerate(texts):
        if text and text.strip():
            valid_contents.append(
                types.Content(
                    parts=[
                        types.Part.from_text(
                            text=text
                        )
                    ]
                )
            )
            valid_indexes.append(index)

    if not valid_contents:
        return results

    try:
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=valid_contents,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIM,
                task_type=task_type,
            ),
        )

        if not response.embeddings:
            raise RuntimeError(
                "Gemini returned no embeddings"
            )

        if len(response.embeddings) != len(valid_contents):
            raise RuntimeError(
                "Gemini returned an unexpected number of embeddings"
            )

        for index, embedding in zip(
            valid_indexes,
            response.embeddings
        ):
            results[index] = embedding.values

        return results

    except Exception as exc:
        print(f"Gemini embedding error: {exc}")

        raise RuntimeError(
            "Failed to generate Gemini embeddings"
        ) from exc