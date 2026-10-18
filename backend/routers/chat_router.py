import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_db
from auth import get_current_user
from ai_service import get_study_chat_response

router = APIRouter(prefix="/api/chat", tags=["Chatbot"])

class ChatQueryRequest(BaseModel):
    message: str

@router.post("/{doc_id}")
def send_chat_message(
    doc_id: int,
    req: ChatQueryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    query = req.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query message cannot be empty.")
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, extracted_pages_json FROM documents WHERE id = ? AND user_id = ?",
            (doc_id, user_id)
        )
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
            
        pages_data = json.loads(doc["extracted_pages_json"])
        doc_title = doc["title"]
        
        # Save user message
        cursor.execute(
            """
            INSERT INTO chat_messages (user_id, document_id, role, content, citations_json, in_document)
            VALUES (?, ?, 'user', ?, '[]', 1)
            """,
            (user_id, doc_id, query)
        )
        
    # Get answer
    res = get_study_chat_response(query, pages_data, current_user, doc_title)
    
    # Save assistant message
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_messages (user_id, document_id, role, content, citations_json, in_document)
            VALUES (?, ?, 'assistant', ?, ?, ?)
            """,
            (
                user_id,
                doc_id,
                res["answer"],
                json.dumps(res.get("citations", [])),
                1 if res.get("in_document", True) else 0
            )
        )
        msg_id = cursor.lastrowid
        
    return {
        "status": "success",
        "message_id": msg_id,
        "answer": res["answer"],
        "citations": res.get("citations", []),
        "in_document": res.get("in_document", True)
    }

@router.get("/{doc_id}/history")
def get_chat_history(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, role, content, citations_json, in_document, created_at 
            FROM chat_messages 
            WHERE document_id = ? AND user_id = ? 
            ORDER BY id ASC
            """,
            (doc_id, user_id)
        )
        rows = cursor.fetchall()
        
        history = []
        for r in rows:
            item = dict(r)
            item["citations"] = json.loads(item["citations_json"] or "[]")
            del item["citations_json"]
            history.append(item)
            
        return history

@router.delete("/{doc_id}/history")
def clear_chat_history(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM chat_messages WHERE document_id = ? AND user_id = ?",
            (doc_id, user_id)
        )
    return {"status": "success", "message": "Chat history cleared."}
