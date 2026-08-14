from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.security import get_current_user
from app.models.user import User
from app.models.document_chunk import DocumentChunk
from app.models.document import Document
from app.schemas.query import QueryRequest, QueryResponse
from app.services.embedding_service import generate_embeddings
from app.services.vector_search import search_similar_chunks
from app.services.rag_service import assemble_context
from app.services.gemini_service import generate_answer


router = APIRouter(
    prefix="",
    tags=["Query"]
)


@router.post(
    "/query",
    response_model=QueryResponse
)
def query_endpoint(
    req: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = req.question.strip()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty",
        )

    # Only retrieve chunks belonging to the logged-in user
    # and containing valid embeddings.
    chunks = (
        db.query(
            DocumentChunk,
            Document.filename
        )
        .join(
            Document,
            Document.id == DocumentChunk.document_id
        )
        .filter(
            Document.user_id == current_user.id,
            DocumentChunk.embedding.isnot(None),
        )
        .all()
    )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No processed document chunks found for user",
        )

    chunk_dicts = []

    for chunk, filename in chunks:
        if not chunk.embedding:
            continue

        chunk_dicts.append(
            {
                "id": chunk.id,
                "document_id": chunk.document_id,
                "content": chunk.content,
                "embedding": chunk.embedding,
                "filename": filename,
            }
        )

    if not chunk_dicts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No document embeddings found for user",
        )

    # Generate embedding for the user's question.
    try:
        query_embeddings = generate_embeddings(
            [question],
            task_type="RETRIEVAL_QUERY",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate query embedding",
        )

    if not query_embeddings or query_embeddings[0] is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate query embedding",
        )

    query_embedding = query_embeddings[0]

    # Retrieve the most similar document chunks.
    results = search_similar_chunks(
        query_embedding=query_embedding,
        chunks=chunk_dicts,
        top_k=req.top_k,
    )

    if not results:
        return {
            "answer": "No relevant information was found in your documents.",
            "sources": [],
        }

    # Build grounded context for Gemini.
    context = assemble_context(results)

    if not context:
        return {
            "answer": "No relevant information was found in your documents.",
            "sources": [],
        }

    # Generate the final answer.
    try:
        generation_result = generate_answer(
            question=question,
            context=context,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate answer",
        )

    if generation_result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate answer",
        )

    answer = generation_result.get("answer")

    if not answer:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini returned an empty answer",
        )

    sources = []

    for result in results:
        sources.append(
            {
                "chunk_id": result["id"],
                "document_id": result["document_id"],
                "filename": result["filename"],
                "score": round(result["score"], 4),
            }
        )

    return {
        "answer": answer,
        "sources": sources,
    }