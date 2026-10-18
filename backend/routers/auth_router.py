from fastapi import APIRouter, HTTPException, Depends, status, Response
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from database import get_db
from auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class SettingsUpdateRequest(BaseModel):
    ai_provider: str
    gemini_api_key: Optional[str] = ""
    openai_api_key: Optional[str] = ""

@router.post("/register")
def register(req: RegisterRequest, response: Response):
    if len(req.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")
        
    hashed = hash_password(req.password)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ? OR username = ?", (req.email.lower(), req.username.strip()))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="An account with this email or username already exists.")
            
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (req.username.strip(), req.email.lower(), hashed)
        )
        user_id = cursor.lastrowid
        
    token = create_access_token({"sub": user_id, "username": req.username.strip()})
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=60*60*24*7)
    
    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "username": req.username.strip(),
            "email": req.email.lower(),
            "ai_provider": "builtin"
        }
    }

@router.post("/login")
def login(req: LoginRequest, response: Response):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email, password_hash, ai_provider FROM users WHERE email = ? OR username = ?",
            (req.email.lower(), req.email)
        )
        user = cursor.fetchone()
        if not user or not verify_password(req.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email/username or password.")
            
        user_id = user["id"]
        username = user["username"]
        email = user["email"]
        ai_provider = user["ai_provider"]
        
    token = create_access_token({"sub": user_id, "username": username})
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=60*60*24*7)
    
    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "username": username,
            "email": email,
            "ai_provider": ai_provider
        }
    }

@router.get("/me")
def me(current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        user_id = current_user["id"]
        cursor.execute("SELECT COUNT(*) as count FROM documents WHERE user_id = ?", (user_id,))
        doc_count = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM revision_notes WHERE user_id = ?", (user_id,))
        notes_count = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count, AVG(score * 100.0 / total) as avg_score FROM quiz_attempts WHERE user_id = ?", (user_id,))
        quiz_row = cursor.fetchone()
        quiz_count = quiz_row["count"] or 0
        avg_score = round(quiz_row["avg_score"] or 0, 1)

    return {
        "user": current_user,
        "stats": {
            "documents_count": doc_count,
            "notes_count": notes_count,
            "quizzes_taken": quiz_count,
            "avg_quiz_score": avg_score
        }
    }

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"status": "success", "message": "Logged out successfully."}

@router.post("/settings/ai")
def update_ai_settings(req: SettingsUpdateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users 
            SET ai_provider = ?, gemini_api_key = ?, openai_api_key = ?
            WHERE id = ?
            """,
            (req.ai_provider, req.gemini_api_key or "", req.openai_api_key or "", user_id)
        )
    return {"status": "success", "message": "AI settings updated successfully."}
