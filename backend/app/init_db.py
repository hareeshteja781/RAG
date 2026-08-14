from app.database import Base, engine
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.conversation import Conversation
from app.models.message import Message

Base.metadata.create_all(bind=engine)

print("Database tables created")