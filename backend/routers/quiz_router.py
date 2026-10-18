import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_db
from auth import get_current_user
from ai_service import get_study_quiz

router = APIRouter(prefix="/api/quiz", tags=["Quizzes"])

class GenerateQuizRequest(BaseModel):
    quiz_type: Optional[str] = "mcq"  # 'mcq', 'true_false', or 'flashcards'
    count: Optional[int] = 5
    difficulty: Optional[str] = "medium"  # 'easy', 'medium', 'hard'

class SubmitQuizRequest(BaseModel):
    answers: Dict[str, str]  # question_id -> selected_option (e.g. {"1": "A", "2": "B"})

@router.post("/{doc_id}/convert-pdf")
@router.post("/{doc_id}/generate")
def generate_quiz(
    doc_id: int,
    req: GenerateQuizRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    count = min(max(req.count or 5, 3), 15)
    difficulty = req.difficulty or "medium"
    
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
        
    items = get_study_quiz(pages_data, req.quiz_type, count, current_user, difficulty=difficulty)
    
    if not items:
        raise HTTPException(
            status_code=400,
            detail="Could not generate questions. Ensure your uploaded document has sufficient text."
        )
        
    type_label = "Flashcards" if req.quiz_type == "flashcards" else ("True/False Quiz" if req.quiz_type == "true_false" else "MCQ Quiz")
    title = f"{type_label} ({difficulty.capitalize()}): {doc_title}"
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO quizzes (user_id, document_id, title, quiz_type, questions_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, doc_id, title, req.quiz_type, json.dumps(items))
        )
        quiz_id = cursor.lastrowid
        
    return {
        "status": "success",
        "quiz_id": quiz_id,
        "title": title,
        "quiz_type": req.quiz_type,
        "items": items
    }

@router.get("/{doc_id}/list")
def list_quizzes_for_doc(
    doc_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, quiz_type, created_at 
            FROM quizzes 
            WHERE document_id = ? AND user_id = ? 
            ORDER BY id DESC
            """,
            (doc_id, user_id)
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@router.get("/detail/{quiz_id}")
def get_quiz_detail(
    quiz_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, document_id, title, quiz_type, questions_json, created_at FROM quizzes WHERE id = ? AND user_id = ?",
            (quiz_id, user_id)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Quiz not found.")
            
        res = dict(row)
        res["items"] = json.loads(res["questions_json"])
        del res["questions_json"]
        return res

@router.post("/{quiz_id}/submit")
def submit_quiz_attempt(
    quiz_id: int,
    req: SubmitQuizRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, document_id, questions_json FROM quizzes WHERE id = ? AND user_id = ?",
            (quiz_id, user_id)
        )
        quiz = cursor.fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found.")
            
        questions = json.loads(quiz["questions_json"])
        total = len(questions)
        score = 0
        detailed_results = []
        
        for q in questions:
            qid_str = str(q["id"])
            user_ans = req.answers.get(qid_str, "")
            correct_ans = q.get("answer", "")
            is_correct = (user_ans.strip().upper() == correct_ans.strip().upper())
            if is_correct:
                score += 1
                
            detailed_results.append({
                "question_id": q["id"],
                "question": q["question"],
                "user_answer": user_ans,
                "correct_answer": correct_ans,
                "is_correct": is_correct,
                "explanation": q.get("explanation", ""),
                "page": q.get("page", 1)
            })
            
        # Save attempt
        cursor.execute(
            """
            INSERT INTO quiz_attempts (user_id, quiz_id, document_id, score, total, answers_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, quiz_id, quiz["document_id"], score, total, json.dumps(detailed_results))
        )
        attempt_id = cursor.lastrowid
        
    percentage = round((score / total) * 100, 1) if total > 0 else 0
    return {
        "status": "success",
        "attempt_id": attempt_id,
        "score": score,
        "total": total,
        "percentage": percentage,
        "results": detailed_results
    }
