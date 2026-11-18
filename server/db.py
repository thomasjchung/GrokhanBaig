"""SQLite storage for watched Instagram accounts, posts, and the event sheet."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "sheet.db"

SEED_ACCOUNT = {
    "username": "farhanandtommyclub",
    "display_name": "Farhan and Tommy Club",
    "bio": "Shows and campus posts from Farhan and Tommy.",
    "instagram_url": "https://www.instagram.com/farhanandtommyclub/",
    "organizer_type": "club",
}


def db_path() -> Path:
    override = os.environ.get("SHEET_DB")
    return Path(override) if override else DEFAULT_DB


def _add_column(conn: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    have = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if name not in have:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    own = conn is None
    conn = conn or connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                last_seen_at TEXT
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                instagram_user_id TEXT,
                display_name TEXT NOT NULL,
                bio TEXT,
                website TEXT,
                organizer_type TEXT NOT NULL DEFAULT 'club',
                instagram_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                status_detail TEXT,
                last_media_id TEXT,
                last_media_at TEXT,
                last_checked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS follows (
                user_id INTEGER NOT NULL REFERENCES users(id),
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, account_id)
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY,
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                media_id TEXT NOT NULL,
                caption TEXT,
                permalink TEXT,
                media_type TEXT,
                posted_at TEXT,
                image_path TEXT,
                UNIQUE (account_id, media_id)
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                account_id INTEGER REFERENCES accounts(id),
                post_id INTEGER UNIQUE REFERENCES posts(id),
                name TEXT NOT NULL,
                tagline TEXT,
                description TEXT,
                starts_at TEXT,
                ends_at TEXT,
                location_name TEXT,
                image_path TEXT,
                organizer_name TEXT,
                organizer_type TEXT,
                instagram_url TEXT,
                partiful_url TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rsvps (
                user_id INTEGER NOT NULL REFERENCES users(id),
                event_id INTEGER NOT NULL REFERENCES events(id),
                status TEXT NOT NULL,
                PRIMARY KEY (user_id, event_id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                gmail_id TEXT NOT NULL UNIQUE,
                account_id INTEGER REFERENCES accounts(id),
                from_email TEXT,
                from_name TEXT,
                subject TEXT,
                received_at TEXT
            );

            CREATE TABLE IF NOT EXISTS oauth_credentials (
                provider TEXT PRIMARY KEY,
                refresh_token TEXT,
                email TEXT,
                last_checked_at TEXT,
                status_detail TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS google_accounts (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                email TEXT NOT NULL,
                refresh_token TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        _add_column(conn, "accounts", "provider", "TEXT NOT NULL DEFAULT 'instagram'")
        _add_column(conn, "accounts", "email", "TEXT")
        _add_column(conn, "users", "email", "TEXT")
        _add_column(conn, "events", "external_id", "TEXT")
        _add_column(conn, "events", "owner_user_id", "INTEGER")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS events_external_id ON events(external_id)"
        )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email ON users(email)")
        conn.execute(
            "INSERT OR IGNORE INTO users (id, name) VALUES (1, 'You')"
        )
        existing = conn.execute(
            "SELECT id FROM accounts WHERE username = ?",
            (SEED_ACCOUNT["username"],),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO accounts (
                    username, display_name, bio, organizer_type, instagram_url, status
                ) VALUES (?, ?, ?, ?, ?, 'ready')
                """,
                (
                    SEED_ACCOUNT["username"],
                    SEED_ACCOUNT["display_name"],
                    SEED_ACCOUNT["bio"],
                    SEED_ACCOUNT["organizer_type"],
                    SEED_ACCOUNT["instagram_url"],
                ),
            )
            account_id = conn.execute(
                "SELECT id FROM accounts WHERE username = ?",
                (SEED_ACCOUNT["username"],),
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT OR IGNORE INTO follows (user_id, account_id, created_at)
                VALUES (1, ?, datetime('now'))
                """,
                (account_id,),
            )
        conn.commit()
    finally:
        if own:
            conn.close()
