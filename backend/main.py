from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate
from app.utils.security import hash_password

from app.routes.auth import router as auth_router
from app.routes.documents import router as documents_router
from app.routes.query import router as query_router
from app.routes.conversations import router as conversations_router


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://enterprise-rag-frontend-teal.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Enterprise RAG API is running"
    }


@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = (
        db.query(User)
        .filter(User.email == user.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    hashed_password = hash_password(user.password)

    new_user = User(
        email=user.email,
        password_hash=hashed_password
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    return {
        "id": new_user.id,
        "email": new_user.email
    }


app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(query_router)
app.include_router(conversations_router)
