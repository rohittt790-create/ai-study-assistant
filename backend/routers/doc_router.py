import os
import json
import time
import shutil
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from database import get_db
from auth import get_current_user
from pdf_service import validate_pdf_file, extract_pdf_data
from sample_data import create_sample_ai_pdf

router = APIRouter(prefix="/api/documents", tags=["Documents"])
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    custom_title: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    content = await file.read()
    
    # 1. Validate file
    validate_pdf_file(file, content)
    
    # 2. Extract pages and word count
    pages_data, page_count, word_count = extract_pdf_data(content)
    
    # Check if empty text / scanned
    if word_count < 10:
        # Still allow upload, but notify
        pass
        
    # 3. Save physical file securely
    clean_filename = f"user{user_id}_{int(time.time())}_{os.path.basename(file.filename or 'notes.pdf')}"
    file_path = os.path.join(UPLOADS_DIR, clean_filename)
    with open(file_path, "wb") as f:
        f.write(content)
        
    title = custom_title.strip() if custom_title and custom_title.strip() else (file.filename or "Study Notes")
    if title.lower().endswith(".pdf"):
        title = title[:-4]
        
    # 4. Save to database
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents (
                user_id, title, filename, file_path, file_size, page_count, word_count, extracted_pages_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                title,
                clean_filename,
                file_path,
                len(content),
                page_count,
                word_count,
                json.dumps(pages_data)
            )
        )
        doc_id = cursor.lastrowid
        
    return {
        "status": "success",
        "message": "Document uploaded and analyzed successfully.",
        "document": {
            "id": doc_id,
            "title": title,
            "filename": clean_filename,
            "page_count": page_count,
            "word_count": word_count,
            "file_size": len(content),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    }

@router.get("")
def list_documents(current_user: Dict[str, Any] = Depends(get_current_user)):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, filename, file_size, page_count, word_count, created_at 
            FROM documents 
            WHERE user_id = ? 
            ORDER BY id DESC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@router.get("/{doc_id}")
def get_document(doc_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, filename, file_size, page_count, word_count, extracted_pages_json, created_at 
            FROM documents 
            WHERE id = ? AND user_id = ?
            """,
            (doc_id, user_id)
        )
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
            
        doc_dict = dict(doc)
        doc_dict["extracted_pages"] = json.loads(doc_dict["extracted_pages_json"])
        del doc_dict["extracted_pages_json"]
        return doc_dict

@router.delete("/{doc_id}")
def delete_document(doc_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
            
        file_path = doc["file_path"]
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
                
        cursor.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
        
    return {"status": "success", "message": "Document deleted successfully."}

@router.post("/load-sample")
def load_sample_document(current_user: Dict[str, Any] = Depends(get_current_user)):
    user_id = current_user["id"]
    pdf_path = create_sample_ai_pdf()
    
    with open(pdf_path, "rb") as f:
        content = f.read()
        
    pages_data, page_count, word_count = extract_pdf_data(content)
    sample_title = "CS101: AI & Machine Learning Foundations (Sample)"
    
    # Check if user already loaded it
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM documents WHERE user_id = ? AND title = ?", (user_id, sample_title))
        existing = cursor.fetchone()
        if existing:
            return {"status": "already_exists", "doc_id": existing["id"]}
            
        cursor.execute(
            """
            INSERT INTO documents (
                user_id, title, filename, file_path, file_size, page_count, word_count, extracted_pages_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                sample_title,
                "CS101_AI_and_Machine_Learning_Notes.pdf",
                pdf_path,
                len(content),
                page_count,
                word_count,
                json.dumps(pages_data)
            )
        )
        doc_id = cursor.lastrowid
        
    return {
        "status": "success",
        "message": "Sample study notes loaded successfully!",
        "doc_id": doc_id
    }
