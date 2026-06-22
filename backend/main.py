from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from dotenv import load_dotenv
import os

load_dotenv()

from models import init_db, get_db, Document, User
from auth import authenticate_user, create_access_token, create_user, get_current_user
from ingestion import save_upload, extract_chunks
from retrieval import embed_and_store, query, delete_document
from qa import answer

app = FastAPI(title="Enterprise Q&A Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ---------- Auth ----------

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(access_token=create_access_token(user.username))


class SignupRequest(BaseModel):
    username: str
    password: str
    admin_secret: str


@app.post("/auth/signup", response_model=TokenResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    expected = os.getenv("ADMIN_SECRET")
    if not expected:
        raise HTTPException(status_code=500, detail="Server not configured for signups")
    if req.admin_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    user = create_user(db, req.username, req.password)
    return TokenResponse(access_token=create_access_token(user.username))


# ---------- Documents ----------

@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    pdf_path = save_upload(file.filename, content)

    chunks = extract_chunks(pdf_path, file.filename)
    chunk_count = embed_and_store(chunks, file.filename)

    # Count pages from chunks
    pages = {c["metadata"]["page"] for c in chunks}

    doc = Document(
        filename=file.filename,
        uploaded_by=current_user.username,
        page_count=max(pages) if pages else 0,
        chunk_count=chunk_count,
    )
    db.add(doc)
    db.commit()

    return {"filename": file.filename, "pages": max(pages) if pages else 0, "chunks": chunk_count}


@app.get("/documents")
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "uploaded_by": d.uploaded_by,
            "uploaded_at": d.uploaded_at.isoformat(),
            "page_count": d.page_count,
            "chunk_count": d.chunk_count,
        }
        for d in docs
    ]


@app.delete("/documents/{doc_id}")
def remove_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_document(doc.filename)
    db.delete(doc)
    db.commit()
    return {"detail": "Document deleted"}


# ---------- Q&A ----------

class QuestionRequest(BaseModel):
    question: str


@app.post("/qa/ask")
def ask(
    req: QuestionRequest,
    current_user: User = Depends(get_current_user),
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    chunks = query(req.question)
    if not chunks:
        return {"answer": "No relevant documents found. Please upload documents first.", "citations": []}
    result = answer(req.question, chunks)
    return result
