from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_db
from auth import get_current_user

router = APIRouter(prefix="/api/notes", tags=["Revision Notes"])

class NoteCreateRequest(BaseModel):
    document_id: Optional[int] = None
    note_type: Optional[str] = "custom"  # 'summary', 'custom', 'chapter', 'bullets'
    title: str
    content: str

class NoteUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

@router.get("")
def list_notes(
    document_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        if document_id:
            cursor.execute(
                """
                SELECT n.id, n.document_id, n.note_type, n.title, n.content, n.created_at, d.title as doc_title
                FROM revision_notes n
                LEFT JOIN documents d ON n.document_id = d.id
                WHERE n.user_id = ? AND n.document_id = ?
                ORDER BY n.id DESC
                """,
                (user_id, document_id)
            )
        else:
            cursor.execute(
                """
                SELECT n.id, n.document_id, n.note_type, n.title, n.content, n.created_at, d.title as doc_title
                FROM revision_notes n
                LEFT JOIN documents d ON n.document_id = d.id
                WHERE n.user_id = ?
                ORDER BY n.id DESC
                """,
                (user_id,)
            )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@router.post("")
def create_note(
    req: NoteCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Note title cannot be empty.")
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO revision_notes (user_id, document_id, note_type, title, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, req.document_id, req.note_type or "custom", req.title.strip(), req.content)
        )
        note_id = cursor.lastrowid
        
    return {"status": "success", "note_id": note_id, "message": "Note created successfully."}

@router.put("/{note_id}")
def update_note(
    note_id: int,
    req: NoteUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM revision_notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Note not found.")
            
        updates = []
        params = []
        if req.title is not None:
            updates.append("title = ?")
            params.append(req.title.strip())
        if req.content is not None:
            updates.append("content = ?")
            params.append(req.content)
            
        if updates:
            params.extend([note_id, user_id])
            query = f"UPDATE revision_notes SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
            cursor.execute(query, tuple(params))
            
    return {"status": "success", "message": "Note updated successfully."}

@router.delete("/{note_id}")
def delete_note(
    note_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM revision_notes WHERE id = ? AND user_id = ?", (note_id, user_id))
    return {"status": "success", "message": "Note deleted successfully."}
