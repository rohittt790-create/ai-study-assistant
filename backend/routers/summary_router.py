import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_db
from auth import get_current_user
from ai_service import get_study_summary

router = APIRouter(prefix="/api/summarize", tags=["Summarization"])

class SummaryRequest(BaseModel):
    length: Optional[str] = "medium"  # 'short', 'medium', 'detailed'
    format_style: Optional[str] = "standard"  # 'standard', 'bullets', 'definitions'
    force_refresh: Optional[bool] = False

class SaveNoteRequest(BaseModel):
    title: str
    content: str
    note_type: Optional[str] = "summary"

@router.post("/{doc_id}")
def summarize_document(
    doc_id: int,
    req: SummaryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, extracted_pages_json, summary_cache_json 
            FROM documents 
            WHERE id = ? AND user_id = ?
            """,
            (doc_id, user_id)
        )
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
            
        pages_data = json.loads(doc["extracted_pages_json"])
        cache = json.loads(doc["summary_cache_json"] or "{}")
        cache_key = f"{req.length}_{req.format_style}"
        
        if not req.force_refresh and cache_key in cache:
            return {
                "status": "success",
                "cached": True,
                "summary": cache[cache_key],
                "length": req.length,
                "format_style": req.format_style,
                "doc_title": doc["title"]
            }
            
    summary_text = get_study_summary(
        pages_data=pages_data,
        length=req.length,
        format_style=req.format_style,
        user=current_user,
        doc_title=doc["title"]
    )
    
    # Update cache
    cache[cache_key] = summary_text
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE documents SET summary_cache_json = ? WHERE id = ?",
            (json.dumps(cache), doc_id)
        )
        
    return {
        "status": "success",
        "cached": False,
        "summary": summary_text,
        "length": req.length,
        "format_style": req.format_style,
        "doc_title": doc["title"]
    }

@router.post("/{doc_id}/save-revision-note")
def save_revision_note(
    doc_id: int,
    req: SaveNoteRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO revision_notes (user_id, document_id, note_type, title, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, doc_id, req.note_type, req.title, req.content)
        )
        note_id = cursor.lastrowid
        
    return {
        "status": "success",
        "message": "Revision note saved successfully!",
        "note_id": note_id
    }
