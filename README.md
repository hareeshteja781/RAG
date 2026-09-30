# Enterprise Multi-Document Q&A System (RAG)

A FastAPI-based RAG application that allows users to upload multiple documents and ask questions grounded in their content.

## Features
- PDF, DOCX, and TXT document ingestion
- Document chunking and processing
- Embedding generation and vector-based retrieval
- Context-aware answers using Gemini
- Source-aware responses
- User authentication and conversation history
- PostgreSQL-backed document and message storage

## Tech Stack
- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Gemini API
- RAG, embeddings, and vector search
- JWT authentication

## Project Structure
```text
backend/
  app/
    models/
    routes/
    schemas/
    services/
    utils/
  main.py
frontend/
```

## Run Locally
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Configure the required database and Gemini API settings using the environment example file.