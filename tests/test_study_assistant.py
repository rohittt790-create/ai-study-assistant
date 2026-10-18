import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend")
sys.path.insert(0, BACKEND_DIR)

from app import app
from database import init_db

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()

@pytest.fixture(scope="session")
def client():
    return TestClient(app)

@pytest.fixture(scope="session")
def auth_context(client):
    unique_id = uuid.uuid4().hex[:8]
    username = f"Student_{unique_id}"
    email = f"student_{unique_id}@university.edu"
    password = "study-password-123"

    resp = client.post("/api/auth/register", json={
        "username": username,
        "email": email,
        "password": password
    })
    assert resp.status_code == 200, f"Register failed: {resp.text}"
    data = resp.json()
    token = data["access_token"]
    user_id = data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "client": client,
        "token": token,
        "user_id": user_id,
        "headers": headers,
        "username": username,
        "email": email,
        "password": password
    }

def test_01_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_02_login_registered_user(client, auth_context):
    resp = client.post("/api/auth/login", json={
        "email": auth_context["email"],
        "password": auth_context["password"]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["id"] == auth_context["user_id"]

def test_03_get_current_user_profile(client, auth_context):
    resp = client.get("/api/auth/me", headers=auth_context["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["id"] == auth_context["user_id"]
    assert "stats" in data
    assert "documents_count" in data["stats"]

def test_04_load_sample_document(client, auth_context):
    resp = client.post("/api/documents/load-sample", headers=auth_context["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "doc_id" in data
    auth_context["doc_id"] = data["doc_id"]

def test_05_list_documents(client, auth_context):
    resp = client.get("/api/documents", headers=auth_context["headers"])
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) >= 1
    assert any(d["id"] == auth_context["doc_id"] for d in docs)

def test_06_get_document_detail_and_pages(client, auth_context):
    doc_id = auth_context["doc_id"]
    resp = client.get(f"/api/documents/{doc_id}", headers=auth_context["headers"])
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["id"] == doc_id
    assert doc["page_count"] >= 3
    assert len(doc["extracted_pages"]) == doc["page_count"]
    assert len(doc["extracted_pages"][0]["text"]) > 40

def test_07_summarize_document(client, auth_context):
    doc_id = auth_context["doc_id"]
    # Short summary
    resp_short = client.post(f"/api/summarize/{doc_id}", json={
        "length": "short",
        "format_style": "standard"
    }, headers=auth_context["headers"])
    assert resp_short.status_code == 200
    assert len(resp_short.json()["summary"]) > 50

    # Bullet summary
    resp_bullets = client.post(f"/api/summarize/{doc_id}", json={
        "length": "medium",
        "format_style": "bullets"
    }, headers=auth_context["headers"])
    assert resp_bullets.status_code == 200
    assert "-" in resp_bullets.json()["summary"]

    # Detailed summary
    resp_detailed = client.post(f"/api/summarize/{doc_id}", json={
        "length": "detailed",
        "format_style": "standard"
    }, headers=auth_context["headers"])
    assert resp_detailed.status_code == 200
    assert "Page" in resp_detailed.json()["summary"]

def test_08_save_summary_as_note(client, auth_context):
    doc_id = auth_context["doc_id"]
    resp = client.post(f"/api/summarize/{doc_id}/save-revision-note", json={
        "title": "CS101 AI Foundations Highlights",
        "content": "# Quick Revision\n- Supervised learning uses labeled data.\n- Neural networks use activation functions.",
        "note_type": "summary"
    }, headers=auth_context["headers"])
    assert resp.status_code == 200
    assert "note_id" in resp.json()

def test_09_chatbot_grounded_qa_with_citations(client, auth_context):
    doc_id = auth_context["doc_id"]
    resp = client.post(f"/api/chat/{doc_id}", json={
        "message": "What is Supervised Learning and what are some common algorithms?"
    }, headers=auth_context["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["in_document"] is True
    assert len(data["citations"]) > 0
    assert data["citations"][0]["page"] >= 1

def test_10_chatbot_out_of_document_fallback(client, auth_context):
    doc_id = auth_context["doc_id"]
    resp = client.post(f"/api/chat/{doc_id}", json={
        "message": "What is the secret recipe for strawberry cheesecake?"
    }, headers=auth_context["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["in_document"] is False
    assert "Not Found in Document" in data["answer"]

def test_11_chatbot_history(client, auth_context):
    doc_id = auth_context["doc_id"]
    resp = client.get(f"/api/chat/{doc_id}/history", headers=auth_context["headers"])
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) >= 2

def test_12_generate_mcq_quiz(client, auth_context):
    doc_id = auth_context["doc_id"]
    resp = client.post(f"/api/quiz/{doc_id}/generate", json={
        "quiz_type": "mcq",
        "count": 5
    }, headers=auth_context["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "quiz_id" in data
    assert len(data["items"]) == 5
    auth_context["quiz_id"] = data["quiz_id"]
    
    first_q = data["items"][0]
    assert "question" in first_q
    assert len(first_q["options"]) == 4
    assert first_q["answer"] in ["A", "B", "C", "D"]
    assert "explanation" in first_q

def test_13_submit_quiz_and_grading(client, auth_context):
    quiz_id = auth_context["quiz_id"]
    detail_resp = client.get(f"/api/quiz/detail/{quiz_id}", headers=auth_context["headers"])
    quiz = detail_resp.json()
    
    first_q = quiz["items"][0]
    answers = {str(first_q["id"]): first_q["answer"]}
    
    submit_resp = client.post(f"/api/quiz/{quiz_id}/submit", json={
        "answers": answers
    }, headers=auth_context["headers"])
    assert submit_resp.status_code == 200
    result = submit_resp.json()
    assert result["score"] >= 1
    assert result["total"] == len(quiz["items"])
    assert "percentage" in result

def test_14_generate_flashcards(client, auth_context):
    doc_id = auth_context["doc_id"]
    resp = client.post(f"/api/quiz/{doc_id}/generate", json={
        "quiz_type": "flashcards",
        "count": 4
    }, headers=auth_context["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 1
    card = data["items"][0]
    assert "front" in card
    assert "back" in card
    assert "page" in card

def test_14b_convert_pdf_endpoint(client, auth_context):
    doc_id = auth_context["doc_id"]
    # Test convert-pdf with difficulty="hard" and count=6
    resp = client.post(f"/api/quiz/{doc_id}/convert-pdf", json={
        "quiz_type": "mcq",
        "count": 6,
        "difficulty": "hard"
    }, headers=auth_context["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "quiz_id" in data
    assert "Hard" in data["title"]
    assert len(data["items"]) >= 1

    # Test convert-pdf with quiz_type="true_false" and difficulty="easy"
    tf_resp = client.post(f"/api/quiz/{doc_id}/convert-pdf", json={
        "quiz_type": "true_false",
        "count": 5,
        "difficulty": "easy"
    }, headers=auth_context["headers"])
    assert tf_resp.status_code == 200
    tf_data = tf_resp.json()
    assert tf_data["status"] == "success"
    assert "quiz_id" in tf_data
    assert len(tf_data["items"]) >= 1
    assert "True/False" in tf_data["title"]

def test_15_revision_notes_crud(client, auth_context):
    headers = auth_context["headers"]
    doc_id = auth_context["doc_id"]

    # List notes
    list_resp = client.get("/api/notes", headers=headers)
    assert list_resp.status_code == 200

    # Create new custom note
    create_resp = client.post("/api/notes", json={
        "document_id": doc_id,
        "title": "Exam Prep Formulas",
        "content": "A* Search formula: f(n) = g(n) + h(n)",
        "note_type": "custom"
    }, headers=headers)
    assert create_resp.status_code == 200
    note_id = create_resp.json()["note_id"]

    # Update note
    update_resp = client.put(f"/api/notes/{note_id}", json={
        "title": "Exam Prep Formulas (Final)"
    }, headers=headers)
    assert update_resp.status_code == 200

    # Delete note
    del_resp = client.delete(f"/api/notes/{note_id}", headers=headers)
    assert del_resp.status_code == 200

def test_16_invalid_file_handling(client, auth_context):
    headers = auth_context["headers"]
    
    # 1. Non-PDF file
    resp_invalid = client.post(
        "/api/documents/upload",
        files={"file": ("notes.docx", b"binary content", "application/octet-stream")},
        headers=headers
    )
    assert resp_invalid.status_code == 400
    assert "Invalid file format" in resp_invalid.json()["detail"]

    # 2. Empty file
    resp_empty = client.post(
        "/api/documents/upload",
        files={"file": ("blank.pdf", b"", "application/pdf")},
        headers=headers
    )
    assert resp_empty.status_code == 400
    assert "empty" in resp_empty.json()["detail"].lower()
