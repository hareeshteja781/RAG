import os
import uuid
import re
import shutil
from datetime import datetime
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.security import get_current_user
from app.models.user import User
from app.models.document import Document
from app.schemas.document import DocumentResponse
from app.models.document_chunk import DocumentChunk
from app.services.document_processor import extract_text
from app.services.chunking import chunk_text
from app.services.embedding_service import generate_embeddings



router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}


def secure_filename(filename: str) -> str:
    name = os.path.basename(filename)
    name = name.replace(' ', '_')
    # replace any character that is not alphanumeric, dot, underscore or hyphen
    return re.sub(r'[^A-Za-z0-9_.-]', '_', name)


def get_uploads_dir() -> str:
    # project root is two levels up from this file (backend)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    uploads_dir = os.path.join(base_dir, 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    return uploads_dir


@router.post("/upload", response_model=DocumentResponse)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    uploads_dir = get_uploads_dir()
    safe_name = secure_filename(file.filename)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    dest_path = os.path.join(uploads_dir, stored_name)

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    try:
        size = os.path.getsize(dest_path)
    except OSError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save file")

    if size == 0:
        try:
            os.remove(dest_path)
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded")

    doc = Document(
        user_id=current_user.id,
        filename=file.filename,
        stored_filename=stored_name,
        file_path=dest_path,
        file_type=file.content_type,
        file_size=size
    )

    db.add(doc)
    db.commit()
    db.refresh(doc)

    return doc


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    docs = db.query(Document).filter(Document.user_id == current_user.id).all()
    return docs


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
        .first()
    )

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    try:
        # Delete all chunks first.
        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).delete(
            synchronize_session=False
        )

        # Delete the document record.
        db.delete(doc)

        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )

    # Remove the physical uploaded file after the database
    # deletion succeeds.
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass

    return {
        "detail": "Document deleted successfully"
    }



@router.post("/{document_id}/process")
def process_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
        .first()
    )

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored document file not found",
        )

    # Mark as processing first.
    doc.processing_status = "processing"
    doc.processed_at = None
    db.commit()

    # --------------------------------------------------
    # 1. Extract text
    # --------------------------------------------------
    try:
        text = extract_text(
            doc.file_path,
            doc.file_type,
        )
    except ValueError:
        doc.processing_status = "failed"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type",
        )
    except Exception:
        doc.processing_status = "failed"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Text extraction failed",
        )

    if not text or not text.strip():
        doc.extracted_text = None
        doc.processing_status = "empty"
        doc.processed_at = None
        db.commit()

        return {
            "detail": "No text found in document"
        }

    # --------------------------------------------------
    # 2. Chunk the extracted text
    # --------------------------------------------------
    chunks = chunk_text(text)

    if not chunks:
        doc.extracted_text = text
        doc.processing_status = "no_chunks"
        doc.processed_at = None
        db.commit()

        return {
            "detail": "No chunks created"
        }

    # --------------------------------------------------
    # 3. Generate embeddings BEFORE deleting old chunks
    # --------------------------------------------------
    try:
        embeddings = generate_embeddings(
            chunks,
            task_type="RETRIEVAL_DOCUMENT",
        )

        if len(embeddings) != len(chunks):
            raise RuntimeError(
                "Embedding count does not match chunk count"
            )

        if any(embedding is None for embedding in embeddings):
            raise RuntimeError(
                "One or more document embeddings were not generated"
            )

    except Exception:
        doc.processing_status = "failed"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document embedding generation failed",
        )

    # --------------------------------------------------
    # 4. Replace old chunks + save new chunks atomically
    # --------------------------------------------------
    try:
        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).delete(
            synchronize_session=False
        )

        for index, (content, embedding) in enumerate(
            zip(chunks, embeddings)
        ):
            db.add(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=index,
                    content=content,
                    embedding=embedding,
                )
            )

        doc.extracted_text = text
        doc.processing_status = "processed"
        doc.processed_at = datetime.utcnow()

        db.commit()

    except SQLAlchemyError:
        db.rollback()

        doc = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.user_id == current_user.id,
            )
            .first()
        )

        if doc:
            doc.processing_status = "failed"
            db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save processed document",
        )

    return {
        "detail": "Document processed successfully",
        "chunks": len(chunks),
    }



@router.get("/{document_id}/text")
def get_document_text(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not doc.extracted_text:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document has not been processed or contains no text")
    return {"document_id": doc.id, "text": doc.extracted_text}
