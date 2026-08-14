import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
)


if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured")


client = genai.Client(api_key=GEMINI_API_KEY)


def generate_answer(
    question: str,
    context: str,
    max_tokens: int = 512
) -> dict:

    system_instruction = (
        "You are an assistant for an enterprise document question-answering system. "
        "Answer the user's question using only the provided document context. "
        "Do not invent facts or use information that is not present in the context. "
        "If the answer cannot be found in the context, clearly say that the answer "
        "is not available in the provided documents."
    )

    prompt = (
        f"Document Context:\n"
        f"{context}\n\n"
        f"User Question:\n"
        f"{question}"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=max_tokens,
                temperature=0.2,
            ),
        )

        answer = response.text

        if not answer:
            return {
                "error": "Gemini returned an empty response"
            }

        return {
            "answer": answer
        }

    except Exception as exc:
        print(f"Gemini generation error: {exc}")

        return {
            "error": "External LLM error"
        }