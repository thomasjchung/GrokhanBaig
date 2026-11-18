"""Sheet API. Opening the app checks the Instagram accounts on your list."""

from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import SEED_ACCOUNT, connect, init_db
from .gmail import (
    GmailError,
    authorization_url,
    client_from_store,
    exchange_code,
    gmail_credentials,
    google_authorization_url,
    google_redirect_uri,
    google_userinfo,
    profile_email,
    sync_gmail,
    take_top_event,
    upsert_google_user,
)
from .instagram import client_from_env, sync_account, valid_username

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DEMO_USER = 1
GMAIL_STATE: set[str] = set()
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SESSION_COOKIE = "sheet_session"
STATE_COOKIE = "google_oauth_state"


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class FollowIn(BaseModel):
    username: str = Field(min_length=1, max_length=30)


class EventIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    tagline: str | None = None
    starts_at: str | None = None
    location_name: str | None = None
    instagram_url: str | None = None


class RsvpIn(BaseModel):
    status: str


def row_account(conn, row, watching: bool) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    upcoming = conn.execute(
        """
        SELECT COUNT(*) AS n FROM events
        WHERE account_id = ? AND starts_at IS NOT NULL AND starts_at >= ?
        """,
        (row["id"], now),
    ).fetchone()["n"]
    provider = row["provider"] if "provider" in row.keys() else "instagram"
    email = row["email"] if "email" in row.keys() else None
    return {
        "username": row["username"],
        "provider": provider or "instagram",
        "email": email,
        "instagram_user_id": row["instagram_user_id"],
        "display_name": row["display_name"],
        "bio": row["bio"],
        "website": row["website"],
        "instagram_url": row["instagram_url"],
        "organizer_type": row["organizer_type"],
        "status": row["status"],
        "status_detail": row["status_detail"],
        "last_checked_at": row["last_checked_at"],
        "upcoming_count": upcoming,
        "watching": watching,
    }


def row_event(conn, row) -> dict:
    going = conn.execute(
        "SELECT COUNT(*) AS n FROM rsvps WHERE event_id = ? AND status = 'going'",
        (row["id"],),
    ).fetchone()["n"]
    mine = conn.execute(
        "SELECT status FROM rsvps WHERE event_id = ? AND user_id = ?",
        (row["id"], DEMO_USER),
    ).fetchone()
    image = f"/media/{row['image_path']}" if row["image_path"] else None
    return {
        "id": row["id"],
        "name": row["name"],
        "tagline": row["tagline"],
        "description": row["description"],
        "starts_at": row["starts_at"],
        "ends_at": row["ends_at"],
        "location_name": row["location_name"],
        "image_url": image,
        "organizer": {
            "name": row["organizer_name"],
            "type": row["organizer_type"] or "club",
        },
        "rsvp": {
            "status": mine["status"] if mine else "none",
            "going_count": going,
        },
        "links": {
            "instagram": row["instagram_url"],
            "partiful": row["partiful_url"],
        },
        "source": source_of(row),
    }


def source_of(row) -> dict | None:
    keys = row.keys()
    if "source_username" not in keys or not row["source_username"]:
        return None
    return {
        "username": row["source_username"],
        "name": row["source_name"],
        "provider": row["source_provider"],
        "email": row["source_email"],
    }


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_env()
    init_db()
    yield


app = FastAPI(title="Sheet", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/accounts")
def search_accounts(q: str = ""):
    term = q.strip().lstrip("@").lower()
    conn = connect()
    try:
        if term:
            rows = conn.execute(
                """
                SELECT * FROM accounts
                WHERE lower(username) LIKE ? OR lower(display_name) LIKE ?
                   OR lower(COALESCE(email, '')) LIKE ?
                ORDER BY CASE WHEN lower(username) = ? THEN 0 ELSE 1 END, username
                LIMIT 20
                """,
                (f"%{term}%", f"%{term}%", f"%{term}%", term),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM accounts ORDER BY username LIMIT 20").fetchall()
        watching = {
            row["account_id"]
            for row in conn.execute(
                "SELECT account_id FROM follows WHERE user_id = ?",
                (DEMO_USER,),
            )
        }
        return {"accounts": [row_account(conn, row, row["id"] in watching) for row in rows]}
    finally:
        conn.close()


@app.get("/api/accounts/{username}")
def get_account(username: str):
    if not valid_username(username):
        raise HTTPException(400, "That username is not valid.")
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM accounts WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "No account with that username.")
        watching = conn.execute(
            "SELECT 1 FROM follows WHERE user_id = ? AND account_id = ?",
            (DEMO_USER, row["id"]),
        ).fetchone()
        posts = conn.execute(
            """
            SELECT caption, permalink, posted_at FROM posts
            WHERE account_id = ? ORDER BY posted_at DESC LIMIT 3
            """,
            (row["id"],),
        ).fetchall()
        profile = row_account(conn, row, watching is not None)
        profile["posts"] = [dict(post) for post in posts]
        event_rows = conn.execute(
            """
            SELECT events.*, accounts.username AS source_username,
                   accounts.provider AS source_provider,
                   accounts.display_name AS source_name,
                   accounts.email AS source_email
            FROM events
            JOIN accounts ON accounts.id = events.account_id
            WHERE events.account_id = ?
              AND events.starts_at IS NOT NULL
              AND events.starts_at >= ?
            ORDER BY events.starts_at
            """,
            (row["id"], datetime.now(timezone.utc).isoformat()),
        ).fetchall()
        profile["events"] = [row_event(conn, event) for event in event_rows]
        return profile
    finally:
        conn.close()


@app.get("/api/me/follows")
def list_follows():
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT accounts.* FROM accounts
            JOIN follows ON follows.account_id = accounts.id
            WHERE follows.user_id = ?
            ORDER BY accounts.display_name
            """,
            (DEMO_USER,),
        ).fetchall()
        return {"accounts": [row_account(conn, row, True) for row in rows]}
    finally:
        conn.close()


@app.post("/api/me/follows")
def follow(body: FollowIn):
    username = body.username.strip().lstrip("@")
    if not valid_username(username):
        raise HTTPException(400, "That username is not valid.")
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id FROM accounts WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Search the directory first. That account is not linked yet.")
        conn.execute(
            """
            INSERT OR IGNORE INTO follows (user_id, account_id, created_at)
            VALUES (?, ?, ?)
            """,
            (DEMO_USER, row["id"], datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return {"watching": True, "username": username}
    finally:
        conn.close()


@app.delete("/api/me/follows/{username}")
def unfollow(username: str):
    if not valid_username(username):
        raise HTTPException(400, "That username is not valid.")
    conn = connect()
    try:
        conn.execute(
            """
            DELETE FROM follows
            WHERE user_id = ? AND account_id = (
                SELECT id FROM accounts WHERE username = ?
            )
            """,
            (DEMO_USER, username),
        )
        conn.commit()
        return {"watching": False, "username": username}
    finally:
        conn.close()


@app.post("/api/checks")
def run_checks(force: bool = False):
    """The login check. Refreshes each watched account whose cursor is stale."""
    conn = connect()
    try:
        now = datetime.now(timezone.utc)
        conn.execute(
            "UPDATE users SET last_seen_at = ? WHERE id = ?",
            (now.isoformat(), DEMO_USER),
        )
        conn.commit()
        rows = conn.execute(
            """
            SELECT accounts.* FROM accounts
            JOIN follows ON follows.account_id = accounts.id
            WHERE follows.user_id = ?
            """,
            (DEMO_USER,),
        ).fetchall()
        graph = client_from_env()
        results = []
        for row in rows:
            provider = row["provider"] if "provider" in row.keys() else "instagram"
            if provider == "email":
                continue
            results.append(sync_account(conn, row, graph, force=force, now=now))
        try:
            gmail = client_from_store(conn)
        except GmailError as error:
            gmail = None
            results.append(
                {
                    "username": "gmail",
                    "status": "error",
                    "new_posts": 0,
                    "new_events": 0,
                    "detail": error.message,
                }
            )
        else:
            results.append(sync_gmail(conn, gmail, force=force, now=now))
        return {"checked_at": now.isoformat(), "accounts": results}
    finally:
        conn.close()


@app.get("/api/events")
def list_events():
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT events.*,
                   accounts.username AS source_username,
                   accounts.provider AS source_provider,
                   accounts.display_name AS source_name,
                   accounts.email AS source_email
            FROM events
            LEFT JOIN accounts ON accounts.id = events.account_id
            LEFT JOIN follows ON follows.account_id = events.account_id AND follows.user_id = ?
            WHERE events.account_id IS NULL OR follows.user_id IS NOT NULL
            ORDER BY events.starts_at IS NULL, events.starts_at, events.id DESC
            """,
            (DEMO_USER,),
        ).fetchall()
        return {"events": [row_event(conn, row) for row in rows]}
    finally:
        conn.close()


@app.post("/api/events")
def create_event(body: EventIn):
    conn = connect()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            """
            INSERT INTO events (
                name, tagline, description, starts_at, location_name,
                organizer_name, organizer_type, instagram_url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'person', ?, ?)
            """,
            (
                body.name.strip(),
                body.tagline,
                body.tagline,
                body.starts_at,
                body.location_name,
                "You",
                body.instagram_url,
                now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM events WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return row_event(conn, row)
    finally:
        conn.close()


@app.post("/api/events/{event_id}/rsvp")
def rsvp(event_id: int, body: RsvpIn):
    if body.status not in {"going", "maybe", "none"}:
        raise HTTPException(400, "Status must be going, maybe, or none.")
    conn = connect()
    try:
        event = conn.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
        if event is None:
            raise HTTPException(404, "No event with that id.")
        if body.status == "none":
            conn.execute(
                "DELETE FROM rsvps WHERE user_id = ? AND event_id = ?",
                (DEMO_USER, event_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO rsvps (user_id, event_id, status) VALUES (?, ?, ?)
                ON CONFLICT(user_id, event_id) DO UPDATE SET status = excluded.status
                """,
                (DEMO_USER, event_id, body.status),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return row_event(conn, row)
    finally:
        conn.close()


def _google_configured() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


@app.get("/api/gmail")
def gmail_status():
    conn = connect()
    try:
        row = gmail_credentials(conn)
        connected = row is not None and bool(row["refresh_token"])
        return {
            "connected": connected,
            "email": row["email"] if connected else None,
            "configured": _google_configured(),
        }
    finally:
        conn.close()


@app.get("/api/gmail/start")
def gmail_start():
    if not _google_configured():
        return HTMLResponse(
            "<p>Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env, "
            "with redirect URI http://127.0.0.1:8000/api/gmail/callback, then try again.</p>",
            status_code=400,
        )
    state = secrets.token_urlsafe(16)
    GMAIL_STATE.add(state)
    return RedirectResponse(authorization_url(state))


@app.get("/api/gmail/callback")
def gmail_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse("/?gmail=denied")
    if not code or state not in GMAIL_STATE:
        raise HTTPException(400, "Gmail sign-in did not match the request that started it.")
    GMAIL_STATE.discard(state)
    try:
        token = exchange_code(code)
    except GmailError as exc:
        raise HTTPException(400, exc.message) from exc
    refresh = token.get("refresh_token")
    email = profile_email(token["access_token"])
    conn = connect()
    try:
        existing = gmail_credentials(conn)
        if not refresh and existing is not None:
            refresh = existing["refresh_token"]
        conn.execute(
            """
            INSERT INTO oauth_credentials (provider, refresh_token, email, last_checked_at, status_detail)
            VALUES ('gmail', ?, ?, NULL, NULL)
            ON CONFLICT(provider) DO UPDATE SET
                refresh_token = excluded.refresh_token,
                email = excluded.email
            """,
            (refresh or "", email),
        )
        conn.commit()
        if refresh and _google_configured():
            from .gmail import GmailClient

            sync_gmail(conn, GmailClient(token["access_token"]), force=True)
    finally:
        conn.close()
    return RedirectResponse("/?gmail=connected")


def _session_user(conn, request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return conn.execute(
        """
        SELECT users.* FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ?
        """,
        (token,),
    ).fetchone()


def _iso_offset(value: str | None) -> str | None:
    if not value:
        return None
    if value.endswith("Z"):
        return value[:-1] + "+00:00"
    return value


def _feed_event(row, *, source: str, reason: str, event_id: str | None = None) -> dict:
    image = None
    if row["image_path"]:
        image = {"url": f"/media/{row['image_path']}", "alt": row["name"]}
    source_url = row["partiful_url"] or row["instagram_url"] or ""
    if source == "Gmail" and not source_url:
        source_url = "https://mail.google.com/"
    organizer = row["organizer_name"] or source
    return {
        "id": event_id or f"{source.lower()}-{row['id']}",
        "title": row["name"],
        "startsAt": _iso_offset(row["starts_at"]) or "",
        "location": row["location_name"] or "New Haven",
        "description": row["description"] or row["tagline"] or "",
        "organizer": {"id": source.lower(), "name": organizer, "iconUrl": None},
        "clubId": source.lower(),
        "sourceLabel": source,
        "sourceUrl": source_url,
        "image": image,
        "friendsGoing": [],
        "reason": {"text": reason},
        "saved": False,
        "going": False,
    }


@app.get("/api/google/session")
def google_session(request: Request):
    conn = connect()
    try:
        user = _session_user(conn, request)
        if user is None or not user["email"]:
            return {"connected": False}
        return {
            "connected": True,
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
        }
    finally:
        conn.close()


@app.get("/api/google/start")
def google_start():
    if not _google_configured():
        return HTMLResponse(
            "<p>Google sign-in needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.</p>",
            status_code=400,
        )
    state = secrets.token_urlsafe(16)
    response = RedirectResponse(google_authorization_url(state))
    response.set_cookie(
        STATE_COOKIE,
        state,
        httponly=True,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


@app.get("/api/google/callback")
def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error or not code or state != request.cookies.get(STATE_COOKIE):
        return RedirectResponse("/?google=denied")
    try:
        token = exchange_code(code, redirect=google_redirect_uri())
        profile = google_userinfo(token["access_token"])
    except GmailError:
        return RedirectResponse("/?google=denied")
    conn = connect()
    try:
        user_id = upsert_google_user(conn, profile["email"], profile.get("name") or profile["email"])
        conn.execute(
            """
            INSERT INTO google_accounts (user_id, email, refresh_token, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                email = excluded.email,
                refresh_token = COALESCE(NULLIF(excluded.refresh_token, ''), google_accounts.refresh_token),
                created_at = excluded.created_at
            """,
            (
                user_id,
                profile["email"].lower(),
                token.get("refresh_token") or "",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        try:
            from .gmail import GmailClient

            take_top_event(
                conn,
                GmailClient(token["access_token"]),
                user_id,
                datetime.now(timezone.utc),
            )
        except GmailError:
            pass
        session_token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (session_token, user_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    response = RedirectResponse("/?google=connected")
    response.delete_cookie(STATE_COOKIE, path="/")
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return response


@app.get("/api/campus/extras")
def campus_extras(request: Request):
    """Instagram events from the seeded account, plus the one Gmail event after sign-in."""
    conn = connect()
    try:
        try:
            graph = client_from_env()
            account = conn.execute(
                "SELECT * FROM accounts WHERE username = ?",
                (SEED_ACCOUNT["username"],),
            ).fetchone()
            if account is not None:
                sync_account(conn, account, graph, force=False)
        except Exception:
            pass
        events = []
        user = _session_user(conn, request)
        if user is not None:
            top = conn.execute(
                "SELECT * FROM events WHERE external_id = ?",
                (f"gmail-top:{user['id']}",),
            ).fetchone()
            if top is not None:
                events.append(
                    _feed_event(top, source="Gmail", reason="From your Gmail.", event_id="gmail-top")
                )
        rows = conn.execute(
            """
            SELECT events.* FROM events
            JOIN accounts ON accounts.id = events.account_id
            WHERE accounts.username = ?
            ORDER BY events.starts_at
            """,
            (SEED_ACCOUNT["username"],),
        ).fetchall()
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            if row["starts_at"] and row["starts_at"] < now:
                continue
            events.append(
                _feed_event(row, source="Instagram", reason="From @farhanandtommyclub.")
            )
        return {"events": events}
    finally:
        conn.close()


app.mount("/media", StaticFiles(directory=ROOT / "data" / "media"), name="media")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/{asset}")
def web_asset(asset: str):
    if asset not in {"app.js", "styles.css"}:
        raise HTTPException(404)
    return FileResponse(WEB / asset)
