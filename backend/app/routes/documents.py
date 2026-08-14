import os
import uuid
import re
import shutil
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.security import get_current_user
from app.models.user import User
from app.models.document import Document
from app.schemas.document import DocumentResponse


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
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # remove physical file
    try:
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception:
        pass

    db.delete(doc)
    db.commit()

    return {"detail": "Document deleted"}
