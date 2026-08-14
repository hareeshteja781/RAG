from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate
from app.utils.security import hash_password
from app.routes.auth import router as auth_router
from app.routes.documents import router as documents_router


app = FastAPI()


@app.get("/")
def root():
    return {"message": "Enterprise RAG API is running"}


@app.post("/users")
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    hashed_password = hash_password(user.password)

    new_user = User(
        email=user.email,
        password_hash=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "email": new_user.email
    }


app.include_router(auth_router)
app.include_router(documents_router)