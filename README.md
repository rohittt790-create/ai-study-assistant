# 🎓 AI Study Assistant

A modern, full-stack, AI-powered Study Assistant Web Application designed to help students learn faster and study more effectively from their notes and PDF documents.

---

## 🌟 Features Overview

### 1. 🔐 User Authentication & Personal Dashboard
- **Secure Registration & Login**: Password hashing with PBKDF2/SHA-256 and JWT session authentication.
- **Personalized Study Dashboard**: Tracks total documents uploaded, revision notes saved, quizzes taken, and average mastery score.
- **User Isolation**: Secure per-user storage for notes, documents, chat histories, and test attempts.
- **One-Click Demo Student Access**: Instant guest entry for fast testing without filling out forms.

### 2. 📄 PDF Upload & Page-by-Page Analysis
- **Drag-and-Drop Uploader**: Clean dropzone with real-time analysis status and progress feedback.
- **Granular Text Extraction**: Extracts and chunks text on a page-by-page basis using `pypdf`, preserving source page references for citations.
- **Robust Validations**: Enforces valid `.pdf` format, protects against corrupt/password-protected files, rejects empty (0-byte) files, and imposes a 25MB safety limit.
- **Pre-Loaded Sample Lecture Notes**: 1-click button loads comprehensive "CS101: Artificial Intelligence & Machine Learning" lecture notes so you can immediately explore all features without finding a PDF on your device.
- **Document Reader**: Inspect extracted text page by page with word count metrics.

### 3. 📝 AI Notes Summarizer & Revision Notes
- **Customizable Lengths**:
  - **⚡ Quick Takeaways (Short)**: Concise executive overview and core thesis.
  - **📖 Core Study Summary (Medium)**: Balanced overview with section highlights and key definitions.
  - **📚 Comprehensive Guide (Detailed)**: Chapter-wise and page-by-page breakdown, key definitions, and exam prep points.
- **Formatting Styles**: Standard structured notes, bullet-point quick revision, and key concepts glossary.
- **Revision Notes Hub**: Save any summary or create custom notes, edit them, search them, and export/print formatted study sheets.

### 4. 💬 AI Study Chatbot with Source Citations
- **Document-Grounded Q&A (RAG)**: Answers questions based directly on the uploaded material using TF-IDF / BM25 semantic chunk retrieval.
- **Direct Page Citations**: Every grounded answer includes citation badges (e.g., `📄 Page 2: "..."`, `📄 Page 4: "..."`).
- **Out-of-Document Handling**: If a student asks a question not present in their notes, the AI clearly flags:
  > *⚠️ Not Found in Document: This topic does not appear in your uploaded notes. Here is general academic information with a clear disclaimer...*
- **Persistent Chat History**: Previous conversations are preserved per document and can be resumed or cleared at any time.

### 5. 🧠 Interactive Quizzes & Spaced Repetition Flashcards
- **Multiple Choice Quiz Mode**:
  - Automatically generates authentic 4-option questions with realistic distractors directly from your study notes.
  - Interactive test taking with instant feedback (Green for correct, Red for incorrect).
  - Detailed explanations citing the exact source page where the concept appears.
  - Real-time score calculator, performance percentage, and retry capability.
- **3D Flip Flashcards Mode**:
  - Spaced repetition flashcards with smooth 3D flip animation.
  - Front: Concept / Definition prompt.
  - Back: Explanation and source page citation.
  - Card navigation controls (Next, Previous, Counter).

### 6. ⚙️ Dual AI Engine (Offline Semantic NLP + External LLMs)
- **Built-in Smart Semantic Engine (Default)**: Runs 100% locally and offline with zero API keys required. Handles semantic retrieval, page ranking, definitions extraction, summaries, and quizzes.
- **Google Gemini & OpenAI Integration**: Enter your Gemini API key (Gemini 2.0 Flash) or OpenAI key in the Settings modal to optionally upgrade to state-of-the-art LLM responses.

---

## 🏗️ Project Architecture

```
ai-study-assistant/
├── backend/
│   ├── app.py                 # FastAPI application & static mount
│   ├── database.py            # SQLite schema, connection pool & migrations
│   ├── auth.py                # JWT authentication & PBKDF2 password hashing
│   ├── pdf_service.py         # PDF text extraction, validation & chunking
│   ├── ai_service.py          # Semantic RAG, summarizer, quizzes & LLM dispatch
│   ├── sample_data.py         # Automated CS101 sample PDF generator
│   └── routers/
│       ├── auth_router.py     # Auth, session, & AI settings endpoints
│       ├── doc_router.py      # PDF upload, document library & sample loader
│       ├── summary_router.py  # AI summarization & notes persistence
│       ├── chat_router.py     # Grounded chatbot Q&A & history
│       ├── quiz_router.py     # Quiz generation, grading & flashcards
│       └── notes_router.py    # Revision notes CRUD
├── frontend/
│   ├── index.html             # Responsive Tailwind CSS student UI
│   ├── app.js                 # Frontend SPA controller & state manager
│   └── styles.css             # Glassmorphism, 3D flip card & markdown styles
├── tests/
│   └── test_study_assistant.py# 16 automated end-to-end integration tests
├── uploads/                   # Stored PDF study materials
├── data/                      # SQLite database storage
├── requirements.txt           # Python dependencies
├── run.sh                     # One-click startup script
└── README.md                  # Documentation
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.9+
- A modern web browser (Chrome, Safari, Firefox, Edge)

### 2. Launch the Application

Run the convenient startup script:
```bash
./run.sh
```

Or manually:
```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Run FastAPI server
python3 -m uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### 3. Open in Browser
Visit: **[http://localhost:8000](http://localhost:8000)**

---

## 🧪 Running Automated Tests

A comprehensive automated test suite covers all 16 core requirements:

```bash
./venv/bin/pytest tests/test_study_assistant.py -v
```

### Test Results
```
tests/test_study_assistant.py::test_01_health_check PASSED               [  6%]
tests/test_study_assistant.py::test_02_login_registered_user PASSED      [ 12%]
tests/test_study_assistant.py::test_03_get_current_user_profile PASSED   [ 18%]
tests/test_study_assistant.py::test_04_load_sample_document PASSED       [ 25%]
tests/test_study_assistant.py::test_05_list_documents PASSED             [ 31%]
tests/test_study_assistant.py::test_06_get_document_detail_and_pages PASSED [ 37%]
tests/test_study_assistant.py::test_07_summarize_document PASSED         [ 43%]
tests/test_study_assistant.py::test_08_save_summary_as_note PASSED       [ 50%]
tests/test_study_assistant.py::test_09_chatbot_grounded_qa_with_citations PASSED [ 56%]
tests/test_study_assistant.py::test_10_chatbot_out_of_document_fallback PASSED [ 62%]
tests/test_study_assistant.py::test_11_chatbot_history PASSED            [ 68%]
tests/test_study_assistant.py::test_12_generate_mcq_quiz PASSED          [ 75%]
tests/test_study_assistant.py::test_13_submit_quiz_and_grading PASSED    [ 81%]
tests/test_study_assistant.py::test_14_generate_flashcards PASSED        [ 87%]
tests/test_study_assistant.py::test_15_revision_notes_crud PASSED        [ 93%]
tests/test_study_assistant.py::test_16_invalid_file_handling PASSED      [100%]

======================== 16 passed in 0.61s =========================
```

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Register new student account |
| `POST` | `/api/auth/login` | Login and receive JWT access token |
| `GET` | `/api/auth/me` | Current user profile and study metrics |
| `POST` | `/api/auth/settings/ai` | Configure AI provider (builtin, Gemini, OpenAI) |
| `POST` | `/api/documents/upload` | Upload PDF and extract page text |
| `GET` | `/api/documents` | List user's uploaded documents |
| `GET` | `/api/documents/{id}` | Get document metadata & page-by-page text |
| `DELETE` | `/api/documents/{id}` | Delete document and associated study data |
| `POST` | `/api/documents/load-sample` | 1-Click load sample CS101 study notes |
| `POST` | `/api/summarize/{doc_id}` | Generate short, medium, or detailed AI summary |
| `POST` | `/api/summarize/{doc_id}/save-revision-note` | Save summary to revision notes |
| `POST` | `/api/chat/{doc_id}` | Ask study chatbot with citations & fallback |
| `GET` | `/api/chat/{doc_id}/history` | Get document chat message history |
| `DELETE` | `/api/chat/{doc_id}/history` | Clear document chat conversation |
| `POST` | `/api/quiz/{doc_id}/generate` | Generate MCQ quiz or 3D flashcards |
| `POST` | `/api/quiz/{quiz_id}/submit` | Submit answers and receive graded scorecard |
| `GET` | `/api/notes` | List saved revision notes |
| `POST` | `/api/notes` | Create custom revision note |
| `PUT` | `/api/notes/{id}` | Edit revision note |
| `DELETE` | `/api/notes/{id}` | Delete revision note |
# ai-study-assistant
