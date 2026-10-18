import os
import re
import json
import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

logger = logging.getLogger("study_assistant.database")

# ==========================================
# CONFIGURATION & PATHS
# ==========================================
IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
if IS_SERVERLESS:
    DB_DIR = "/tmp/study_assistant_data"
else:
    DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

try:
    os.makedirs(DB_DIR, exist_ok=True)
except Exception:
    DB_DIR = "/tmp/study_assistant_data"
    os.makedirs(DB_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, "study_assistant.db")

MONGO_URI = os.environ.get("MONGO_URI", "").strip()
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "study_assistant").strip()

_mongo_client: Optional[Any] = None
_mongo_db: Optional[Any] = None
_mongo_connected: bool = False

TABLES = ["users", "documents", "chat_messages", "quizzes", "quiz_attempts", "revision_notes"]

# ==========================================
# MONGODB CLIENT & CONNECTION
# ==========================================
def get_mongo_client():
    global _mongo_client, _mongo_connected
    if _mongo_client is not None:
        return _mongo_client

    if not MONGO_URI:
        _mongo_connected = False
        return None

    try:
        import pymongo
        client = pymongo.MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=4000,
            connectTimeoutMS=4000
        )
        # Test connection
        client.admin.command("ping")
        _mongo_client = client
        _mongo_connected = True
        return _mongo_client
    except Exception as e:
        logger.warning(f"Could not connect to MongoDB Atlas ({e}). Operating in resilient local mode.")
        _mongo_connected = False
        return None

def get_mongo_db():
    global _mongo_db
    if _mongo_db is not None:
        return _mongo_db
    client = get_mongo_client()
    if client is not None:
        _mongo_db = client[MONGO_DB_NAME]
        return _mongo_db
    return None

def is_mongo_connected() -> bool:
    global _mongo_connected
    try:
        client = get_mongo_client()
        if client is not None:
            client.admin.command("ping")
            _mongo_connected = True
            return True
    except Exception:
        _mongo_connected = False
    return False

def get_db_status() -> Dict[str, Any]:
    connected = is_mongo_connected()
    db = get_mongo_db() if connected else None
    counts = {}
    if db is not None:
        for t in TABLES:
            try:
                counts[t] = db[t].count_documents({})
            except Exception:
                counts[t] = 0

    return {
        "engine": "MongoDB Atlas",
        "cluster": "cluster0.r2wn6ka.mongodb.net",
        "database_name": MONGO_DB_NAME,
        "connected": connected,
        "counts": counts,
        "resilient_local_mirror": os.path.exists(DB_PATH)
    }

# ==========================================
# DATA SYNC LOGIC (SQLITE <-> MONGODB)
# ==========================================
def format_doc_for_mongo(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(row_dict)
    doc["_id"] = doc["id"]
    for k in ["extracted_pages_json", "summary_cache_json", "citations_json", "questions_json", "answers_json"]:
        if k in doc and doc[k]:
            clean_key = k.replace("_json", "")
            try:
                doc[clean_key] = json.loads(doc[k])
            except Exception:
                pass
    return doc

def sync_row_to_mongo(table: str, row_dict: Dict[str, Any]):
    db = get_mongo_db()
    if db is None:
        return
    try:
        doc = format_doc_for_mongo(row_dict)
        db[table].replace_one({"_id": doc["_id"]}, doc, upsert=True)
    except Exception as e:
        logger.warning(f"Failed to sync row to Mongo table {table}: {e}")

def sync_delete_to_mongo(table: str, sql: str, params: tuple):
    db = get_mongo_db()
    if db is None:
        return
    try:
        clean = sql.strip().upper()
        if "WHERE ID = ?" in clean and len(params) >= 1:
            row_id = params[0]
            db[table].delete_one({"_id": row_id})
            if table == "documents":
                db["chat_messages"].delete_many({"document_id": row_id})
                db["quizzes"].delete_many({"document_id": row_id})
                db["quiz_attempts"].delete_many({"document_id": row_id})
                db["revision_notes"].delete_many({"document_id": row_id})
        elif "WHERE DOCUMENT_ID = ?" in clean and len(params) >= 1:
            doc_id = params[0]
            db[table].delete_many({"document_id": doc_id})
        elif len(params) >= 1:
            db[table].delete_one({"_id": params[0]})
    except Exception as e:
        logger.warning(f"Failed to sync delete to Mongo table {table}: {e}")

def sync_all_from_mongo_to_sqlite():
    db = get_mongo_db()
    if db is None:
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Sync users
        for u in db.users.find({}):
            cursor.execute("SELECT id FROM users WHERE id = ?", (u["id"],))
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO users (id, username, email, password_hash, ai_provider, gemini_api_key, openai_api_key, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        u["id"],
                        u["username"],
                        u["email"],
                        u["password_hash"],
                        u.get("ai_provider", "builtin"),
                        u.get("gemini_api_key", ""),
                        u.get("openai_api_key", ""),
                        u.get("created_at", "")
                    )
                )

        # Sync documents
        for d in db.documents.find({}):
            cursor.execute("SELECT id FROM documents WHERE id = ?", (d["id"],))
            if not cursor.fetchone():
                pages_json = d.get("extracted_pages_json") or json.dumps(d.get("extracted_pages", []))
                summary_cache = d.get("summary_cache_json") or json.dumps(d.get("summary_cache", {}))
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO documents (id, user_id, title, filename, file_path, file_size, page_count, word_count, extracted_pages_json, summary_cache_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        d["id"],
                        d["user_id"],
                        d["title"],
                        d["filename"],
                        d["file_path"],
                        d["file_size"],
                        d["page_count"],
                        d.get("word_count", 0),
                        pages_json,
                        summary_cache,
                        d.get("created_at", "")
                    )
                )

        # Sync chat_messages
        for m in db.chat_messages.find({}):
            cursor.execute("SELECT id FROM chat_messages WHERE id = ?", (m["id"],))
            if not cursor.fetchone():
                citations_json = m.get("citations_json") or json.dumps(m.get("citations", []))
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO chat_messages (id, user_id, document_id, role, content, citations_json, in_document, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        m["id"],
                        m["user_id"],
                        m["document_id"],
                        m["role"],
                        m["content"],
                        citations_json,
                        m.get("in_document", 1),
                        m.get("created_at", "")
                    )
                )

        # Sync quizzes
        for q in db.quizzes.find({}):
            cursor.execute("SELECT id FROM quizzes WHERE id = ?", (q["id"],))
            if not cursor.fetchone():
                questions_json = q.get("questions_json") or json.dumps(q.get("questions", []))
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO quizzes (id, user_id, document_id, title, quiz_type, questions_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        q["id"],
                        q["user_id"],
                        q["document_id"],
                        q["title"],
                        q["quiz_type"],
                        questions_json,
                        q.get("created_at", "")
                    )
                )

        # Sync quiz_attempts
        for qa in db.quiz_attempts.find({}):
            cursor.execute("SELECT id FROM quiz_attempts WHERE id = ?", (qa["id"],))
            if not cursor.fetchone():
                answers_json = qa.get("answers_json") or json.dumps(qa.get("answers", []))
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO quiz_attempts (id, user_id, quiz_id, document_id, score, total, answers_json, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        qa["id"],
                        qa["user_id"],
                        qa["quiz_id"],
                        qa["document_id"],
                        qa["score"],
                        qa["total"],
                        answers_json,
                        qa.get("completed_at", "")
                    )
                )

        # Sync revision_notes
        for n in db.revision_notes.find({}):
            cursor.execute("SELECT id FROM revision_notes WHERE id = ?", (n["id"],))
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO revision_notes (id, user_id, document_id, note_type, title, content, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        n["id"],
                        n["user_id"],
                        n["document_id"],
                        n.get("note_type", "custom"),
                        n["title"],
                        n["content"],
                        n.get("created_at", "")
                    )
                )

        conn.commit()
    except Exception as e:
        logger.warning(f"Error syncing from Mongo to SQLite: {e}")
    finally:
        conn.close()

def sync_all_from_sqlite_to_mongo():
    db = get_mongo_db()
    if db is None:
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        for t in TABLES:
            cursor.execute(f"SELECT * FROM {t}")
            rows = cursor.fetchall()
            col = db[t]
            for r in rows:
                doc = format_doc_for_mongo(dict(r))
                col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    except Exception as e:
        logger.warning(f"Error syncing from SQLite to Mongo: {e}")
    finally:
        conn.close()

# ==========================================
# CURSOR & CONNECTION PROXIES FOR REAL-TIME SYNC
# ==========================================
class MongoSyncCursor:
    def __init__(self, cursor, conn_proxy):
        self._cursor = cursor
        self._conn_proxy = conn_proxy

    def execute(self, sql: str, params: tuple = ()):
        res = self._cursor.execute(sql, params)
        clean = sql.strip()

        # Check for INSERT
        m_ins = re.match(r"INSERT\s+INTO\s+([a-zA-Z0-9_]+)", clean, re.IGNORECASE)
        if m_ins:
            table = m_ins.group(1).lower()
            if table in TABLES:
                rowid = self._cursor.lastrowid
                self._conn_proxy.pending_inserts.append((table, rowid))

        # Check for UPDATE
        m_upd = re.match(r"UPDATE\s+([a-zA-Z0-9_]+)", clean, re.IGNORECASE)
        if m_upd:
            table = m_upd.group(1).lower()
            if table in TABLES:
                self._conn_proxy.pending_updates.append((table, clean, params))

        # Check for DELETE
        m_del = re.match(r"DELETE\s+FROM\s+([a-zA-Z0-9_]+)", clean, re.IGNORECASE)
        if m_del:
            table = m_del.group(1).lower()
            if table in TABLES:
                self._conn_proxy.pending_deletes.append((table, clean, params))

        return res

    def executemany(self, sql: str, seq_of_parameters):
        return self._cursor.executemany(sql, seq_of_parameters)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return self._cursor.fetchmany(size)

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def close(self):
        return self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)

class MongoSyncConnection:
    def __init__(self, conn):
        self._conn = conn
        self.pending_inserts: List[tuple] = []
        self.pending_updates: List[tuple] = []
        self.pending_deletes: List[tuple] = []

    def cursor(self):
        return MongoSyncCursor(self._conn.cursor(), self)

    def execute(self, sql: str, params: tuple = ()):
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor

    def commit(self):
        self._conn.commit()

        # Real-time synchronization to MongoDB Atlas
        if is_mongo_connected():
            read_cursor = self._conn.cursor()

            # Handle Inserts
            for table, rowid in self.pending_inserts:
                try:
                    read_cursor.execute(f"SELECT * FROM {table} WHERE id = ?", (rowid,))
                    row = read_cursor.fetchone()
                    if row:
                        sync_row_to_mongo(table, dict(row))
                except Exception as e:
                    logger.warning(f"Error syncing insert to Mongo: {e}")

            # Handle Updates
            for table, sql, params in self.pending_updates:
                try:
                    # If WHERE id = ? was used, sync the specific row
                    m = re.search(r"WHERE\s+.*?id\s*=\s*\?", sql, re.IGNORECASE)
                    if m and params:
                        row_id = params[-1]
                        read_cursor.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
                        row = read_cursor.fetchone()
                        if row:
                            sync_row_to_mongo(table, dict(row))
                    else:
                        # Fallback sync whole table
                        read_cursor.execute(f"SELECT * FROM {table}")
                        for r in read_cursor.fetchall():
                            sync_row_to_mongo(table, dict(r))
                except Exception as e:
                    logger.warning(f"Error syncing update to Mongo: {e}")

            # Handle Deletes
            for table, sql, params in self.pending_deletes:
                try:
                    sync_delete_to_mongo(table, sql, params)
                except Exception as e:
                    logger.warning(f"Error syncing delete to Mongo: {e}")

        # Clear pending queue
        self.pending_inserts.clear()
        self.pending_updates.clear()
        self.pending_deletes.clear()

    def rollback(self):
        self.pending_inserts.clear()
        self.pending_updates.clear()
        self.pending_deletes.clear()
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()

# ==========================================
# DATABASE CONTEXT MANAGER & INIT
# ==========================================
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    proxy = MongoSyncConnection(conn)
    try:
        yield proxy
        proxy.commit()
    except Exception:
        proxy.rollback()
        raise
    finally:
        proxy.close()

def init_db():
    # 1. Initialize SQLite schema
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            ai_provider TEXT DEFAULT 'builtin',
            gemini_api_key TEXT DEFAULT '',
            openai_api_key TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            page_count INTEGER NOT NULL,
            word_count INTEGER DEFAULT 0,
            extracted_pages_json TEXT NOT NULL,
            summary_cache_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            citations_json TEXT DEFAULT '[]',
            in_document INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            quiz_type TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            answers_json TEXT DEFAULT '[]',
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS revision_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            note_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()

    # 2. Connect to MongoDB Atlas and synchronize
    try:
        mongo_db = get_mongo_db()
        if mongo_db is not None:
            # Create unique indexes
            mongo_db.users.create_index("email", unique=True)
            mongo_db.users.create_index("username", unique=True)

            # Bidirectional sync: Pull existing from Mongo if local is fresh
            user_count_mongo = mongo_db.users.count_documents({})
            if user_count_mongo > 0:
                sync_all_from_mongo_to_sqlite()

            # Ensure all local records are safely pushed to Mongo
            sync_all_from_sqlite_to_mongo()
            print(f"[Database] MongoDB Atlas Connected & Synchronized (Cluster: cluster0.r2wn6ka.mongodb.net / DB: {MONGO_DB_NAME})")
        else:
            print("[Database] Operating with local database mirror.")
    except Exception as e:
        print(f"[Database] MongoDB initialization notice: {e}")

if __name__ == "__main__":
    init_db()
    print("Database initialized. Status:", get_db_status())
