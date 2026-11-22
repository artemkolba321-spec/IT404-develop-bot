import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/requests.sqlite")
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)


def connect():
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def init_db():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT NOT NULL,
                telegram_username TEXT,
                github_username TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT,
                reviewed_by TEXT,
                github_invitation_sent_at TEXT,
                UNIQUE(telegram_id, github_username)
            );
            CREATE INDEX IF NOT EXISTS idx_access_requests_telegram
                ON access_requests (telegram_id, created_at DESC);
        """)


def create_request(telegram_id, telegram_username, github_username):
    with connect() as db:
        db.execute("""
            INSERT INTO access_requests (telegram_id, telegram_username, github_username)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id, github_username) DO UPDATE SET
                status = CASE
                    WHEN access_requests.status IN ('rejected', 'cancelled') THEN 'pending'
                    ELSE access_requests.status
                END
        """, (str(telegram_id), telegram_username, github_username))
        return db.execute("""
            SELECT * FROM access_requests
            WHERE telegram_id = ? AND github_username = ?
        """, (str(telegram_id), github_username)).fetchone()


def get_request(request_id):
    with connect() as db:
        return db.execute(
            "SELECT * FROM access_requests WHERE id = ?", (request_id,)
        ).fetchone()


def get_latest_for_telegram(telegram_id):
    with connect() as db:
        return db.execute("""
            SELECT * FROM access_requests
            WHERE telegram_id = ? ORDER BY id DESC LIMIT 1
        """, (str(telegram_id),)).fetchone()


def list_pending(limit=10):
    with connect() as db:
        return db.execute("""
            SELECT * FROM access_requests
            WHERE status = 'pending' ORDER BY id ASC LIMIT ?
        """, (limit,)).fetchall()


def set_status(request_id, status, reviewer, invitation_sent=False):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        return db.execute("""
            UPDATE access_requests
            SET status = ?, reviewed_at = ?, reviewed_by = ?,
                github_invitation_sent_at = CASE
                    WHEN ? THEN ? ELSE github_invitation_sent_at
                END
            WHERE id = ?
        """, (status, now, str(reviewer), int(invitation_sent), now, request_id)).rowcount
