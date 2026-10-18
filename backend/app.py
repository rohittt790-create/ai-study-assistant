import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import init_db, get_db_status
from routers import auth_router, doc_router, summary_router, chat_router, quiz_router, notes_router

# Initialize database
init_db()

app = FastAPI(
    title="AI Study Assistant API",
    description="Backend API for AI-powered Study Assistant Web Application",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router.router)
app.include_router(doc_router.router)
app.include_router(summary_router.router)
app.include_router(chat_router.router)
app.include_router(quiz_router.router)
app.include_router(notes_router.router)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

# Health check & Database status
@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "app": "AI Study Assistant",
        "version": "1.0.0",
        "database": get_db_status()
    }

@app.get("/api/database/status")
def database_status():
    return get_db_status()

# Static files & SPA root
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Study Assistant API is running. Frontend not found."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
