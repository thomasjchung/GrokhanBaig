"""Read upcoming events out of Gmail and group them by sender.

One From address is one profile. A second invite from that address is another
event on the same profile, not a second profile.
"""

from __future__ import annotations

import base64
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from .extract import parse_caption

GMAIL_QUERY = (
    "in:inbox newer_than:60d ("
    "filename:ics OR subject:invite OR subject:invitation OR subject:rsvp "
    'OR subject:ticket OR subject:"you\'re invited" OR from:partiful.com '
    "OR from:lu.ma OR from:luma.com OR subject:showcase OR subject:performance)"
)
STALE_MINUTES = 15
FROM_RE = re.compile(r"(.*?)<([^>]+)>")
PARTIFUL_RE = re.compile(r"https://partiful\.com/e/[A-Za-z0-9_-]+")
SLUG_RE = re.compile(r"[^a-z0-9._]+")


class GmailError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def slug_for(email: str) -> str:
    local, _, domain = email.lower().partition("@")
    host = domain.split(".")[0] if domain else "mail"
    raw = SLUG_RE.sub(".", f"{local}.{host}").strip(".")
    return (raw or "sender")[:30]


def unique_slug(conn, email: str) -> str:
    base = slug_for(email)
    slug = base
    number = 2
    while conn.execute(
        "SELECT 1 FROM accounts WHERE username = ? AND COALESCE(email, '') != ?",
        (slug, email.lower()),
    ).fetchone():
        suffix = f".{number}"
        slug = base[: 30 - len(suffix)] + suffix
        number += 1
    return slug


def decode_data(data: str | None) -> str:
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def header(headers: list[dict], name: str) -> str:
    for item in headers or []:
        if item.get("name", "").lower() == name.lower():
            return item.get("value") or ""
    return ""


def parse_from(value: str) -> tuple[str, str]:
    match = FROM_RE.search(value or "")
    if match:
        name = match.group(1).strip().strip('"')
        return name or match.group(2), match.group(2).strip().lower()
    email = (value or "").strip().lower()
    return email, email


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
    )
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def collect_parts(part: dict, found: dict) -> None:
    mime = part.get("mimeType") or ""
    filename = part.get("filename") or ""
    data = decode_data((part.get("body") or {}).get("data"))
    if data and (mime == "text/calendar" or filename.lower().endswith(".ics")):
        found["ics"].append(data)
    elif data and mime == "text/plain":
        found["plain"].append(data)
    elif data and mime == "text/html":
        found["html"].append(data)
    for child in part.get("parts") or []:
        collect_parts(child, found)


def unfold_ics(text: str) -> str:
    return re.sub(r"\r?\n[ \t]", "", text.replace("\r\n", "\n"))


def unescape_ics(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def parse_ics_when(params: dict, value: str) -> datetime | None:
    raw = value.strip()
    try:
        if raw.endswith("Z"):
            parsed = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        elif "T" in raw:
            parsed = datetime.strptime(raw, "%Y%m%dT%H%M%S")
        else:
            parsed = datetime.strptime(raw, "%Y%m%d")
    except ValueError:
        return None
    if parsed.tzinfo is None:
        tzid = params.get("TZID") or "America/New_York"
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(tzid))
        except Exception:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def vevents(text: str) -> list[dict]:
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfold_ics(text), re.S):
        fields: dict[str, list[tuple[dict, str]]] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            left, value = line.split(":", 1)
            name, *params = left.split(";")
            param_map = {}
            for param in params:
                if "=" in param:
                    key, item = param.split("=", 1)
                    param_map[key] = item
            fields.setdefault(name.upper(), []).append((param_map, unescape_ics(value)))
        events.append(fields)
    return events


def field(event: dict, name: str) -> tuple[dict, str]:
    values = event.get(name) or [({}, "")]
    return values[0]


def ics_events(text: str) -> list[dict]:
    drafted = []
    for event in vevents(text):
        status = field(event, "STATUS")[1].upper()
        if status == "CANCELLED":
            continue
        params, start_raw = field(event, "DTSTART")
        starts = parse_ics_when(params, start_raw) if start_raw else None
        end_params, end_raw = field(event, "DTEND")
        ends = parse_ics_when(end_params, end_raw) if end_raw else None
        summary = field(event, "SUMMARY")[1].strip() or "Invite"
        location = field(event, "LOCATION")[1].strip() or None
        description = field(event, "DESCRIPTION")[1].strip()
        url = field(event, "URL")[1].strip()
        uid = field(event, "UID")[1].strip()
        partiful = PARTIFUL_RE.search(description or "") or PARTIFUL_RE.search(url or "")
        drafted.append(
            {
                "name": summary[:120],
                "tagline": (description or "")[:180] or None,
                "description": description or summary,
                "starts_at": starts.isoformat() if starts else None,
                "ends_at": ends.isoformat() if ends else None,
                "location_name": location,
                "partiful_url": partiful.group(0) if partiful else (url if "partiful.com" in url else None),
                "uid": uid,
            }
        )
    return drafted


def as_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("America/New_York"))
    return parsed.astimezone(timezone.utc)


def is_upcoming(value: str | None, now: datetime) -> bool:
    parsed = as_utc(value)
    if parsed is None:
        return False
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return parsed >= now.astimezone(timezone.utc)


def text_event(subject: str, body: str, received: datetime, sender_name: str) -> dict | None:
    caption = "\n".join(part for part in (subject, body) if part).strip()
    drafted = parse_caption(caption, received, sender_name or "mail", sender_name or "mail")
    if drafted is None:
        return None
    partiful = PARTIFUL_RE.search(caption)
    drafted["partiful_url"] = partiful.group(0) if partiful else None
    drafted["uid"] = ""
    if drafted.get("starts_at"):
        drafted["starts_at"] = as_utc(drafted["starts_at"]).isoformat()
    if drafted.get("ends_at"):
        drafted["ends_at"] = as_utc(drafted["ends_at"]).isoformat()
    return drafted


def drafts_from_message(message: dict, received: datetime, sender_name: str) -> list[dict]:
    found = {"ics": [], "plain": [], "html": []}
    collect_parts(message.get("payload") or {}, found)
    drafted = []
    for blob in found["ics"]:
        drafted.extend(ics_events(blob))
    if drafted:
        return drafted
    body = "\n".join(found["plain"]) or html_to_text("\n".join(found["html"]))
    subject = header((message.get("payload") or {}).get("headers"), "Subject")
    one = text_event(subject, body, received, sender_name)
    return [one] if one else []


def ensure_sender(conn, email: str, name: str) -> sqlite3_row:
    email = email.lower()
    row = conn.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
    display = name.strip() if name and "@" not in name else email
    if row is not None:
        weak = row["display_name"].lower() in {email, "noreply", "no-reply", ""}
        if display and weak:
            conn.execute(
                "UPDATE accounts SET display_name = ? WHERE id = ?",
                (display, row["id"]),
            )
            row = conn.execute("SELECT * FROM accounts WHERE id = ?", (row["id"],)).fetchone()
        return row
    username = unique_slug(conn, email)
    conn.execute(
        """
        INSERT INTO accounts (
            username, display_name, bio, organizer_type, instagram_url,
            status, provider, email
        ) VALUES (?, ?, ?, 'person', '', 'ok', 'email', ?)
        """,
        (username, display or email, f"Invites from {email}", email),
    )
    account_id = conn.execute(
        "SELECT id FROM accounts WHERE email = ?",
        (email,),
    ).fetchone()["id"]
    conn.execute(
        """
        INSERT OR IGNORE INTO follows (user_id, account_id, created_at)
        VALUES (1, ?, datetime('now'))
        """,
        (account_id,),
    )
    return conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()


# Hint for type checkers without importing sqlite3 at runtime in annotations.
sqlite3_row = object


def store_event(conn, account, drafted: dict, external_id: str, now: datetime) -> bool:
    if not is_upcoming(drafted.get("starts_at"), now):
        return False
    if conn.execute(
        "SELECT 1 FROM events WHERE external_id = ?",
        (external_id,),
    ).fetchone():
        return False
    conn.execute(
        """
        INSERT INTO events (
            account_id, name, tagline, description, starts_at, ends_at,
            location_name, organizer_name, organizer_type, instagram_url,
            partiful_url, created_at, external_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'person', '', ?, ?, ?)
        """,
        (
            account["id"],
            drafted["name"][:120],
            drafted.get("tagline"),
            drafted.get("description"),
            as_utc(drafted.get("starts_at")).isoformat(),
            as_utc(drafted["ends_at"]).isoformat() if as_utc(drafted.get("ends_at")) else None,
            drafted.get("location_name"),
            account["display_name"],
            drafted.get("partiful_url"),
            now.isoformat(),
            external_id,
        ),
    )
    return True


def ingest_message(conn, message: dict, now: datetime) -> int:
    gmail_id = message.get("id") or ""
    if not gmail_id:
        return 0
    if conn.execute("SELECT 1 FROM messages WHERE gmail_id = ?", (gmail_id,)).fetchone():
        return 0
    payload = message.get("payload") or {}
    sender_name, sender_email = parse_from(header(payload.get("headers"), "From"))
    if "@" not in sender_email:
        return 0
    received_ms = message.get("internalDate")
    if received_ms:
        received = datetime.fromtimestamp(int(received_ms) / 1000, tz=timezone.utc)
    else:
        received = now
    drafts = drafts_from_message(message, received, sender_name)
    upcoming = [item for item in drafts if is_upcoming(item.get("starts_at"), now)]
    subject = header(payload.get("headers"), "Subject")
    if not upcoming:
        conn.execute(
            """
            INSERT OR IGNORE INTO messages (gmail_id, account_id, from_email, from_name, subject, received_at)
            VALUES (?, NULL, ?, ?, ?, ?)
            """,
            (gmail_id, sender_email, sender_name, subject[:300], received.isoformat()),
        )
        return 0
    account = ensure_sender(conn, sender_email, sender_name)
    created = 0
    for index, drafted in enumerate(upcoming):
        uid = drafted.get("uid") or str(index)
        if store_event(conn, account, drafted, f"{gmail_id}:{uid}", now):
            created += 1
    conn.execute(
        """
        INSERT OR IGNORE INTO messages (gmail_id, account_id, from_email, from_name, subject, received_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (gmail_id, account["id"], sender_email, sender_name, subject[:300], received.isoformat()),
    )
    return created


class GmailClient:
    def __init__(self, token: str):
        self.token = token

    def list_ids(self, query: str | None = None, limit: int = 25) -> list[str]:
        response = httpx.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            params={"q": query or GMAIL_QUERY, "maxResults": limit},
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=25,
        )
        body = response.json()
        if response.status_code >= 400:
            error = body.get("error", {}).get("message") or response.text
            raise GmailError(error[:280])
        return [item["id"] for item in body.get("messages") or []]

    def get_message(self, message_id: str) -> dict:
        response = httpx.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            params={"format": "full"},
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=25,
        )
        body = response.json()
        if response.status_code >= 400:
            error = body.get("error", {}).get("message") or response.text
            raise GmailError(error[:280])
        return body


def redirect_uri() -> str:
    return os.environ.get("GMAIL_REDIRECT_URI", "http://127.0.0.1:8000/api/gmail/callback")


GOOGLE_SIGNIN_SCOPE = "openid email profile https://www.googleapis.com/auth/gmail.readonly"


def google_redirect_uri() -> str:
    return os.environ.get("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5174/api/google/callback")


def _auth_url(state: str, scope: str, redirect: str) -> str:
    from urllib.parse import urlencode

    query = urlencode(
        {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": scope,
            "access_type": "offline",
            "prompt": "select_account consent",
            "state": state,
        }
    )
    return "https://accounts.google.com/o/oauth2/v2/auth?" + query


def authorization_url(state: str) -> str:
    return _auth_url(state, "https://www.googleapis.com/auth/gmail.readonly", redirect_uri())


def google_authorization_url(state: str) -> str:
    return _auth_url(state, GOOGLE_SIGNIN_SCOPE, google_redirect_uri())


def exchange_code(code: str, redirect: str | None = None) -> dict:
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "redirect_uri": redirect or redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=25,
    )
    body = response.json()
    if response.status_code >= 400 or "access_token" not in body:
        raise GmailError(body.get("error_description") or "Google did not return a token.")
    return body


def google_userinfo(access_token: str) -> dict:
    response = httpx.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=25,
    )
    if response.status_code >= 400:
        raise GmailError("Google did not share the account.")
    body = response.json()
    if not body.get("email"):
        raise GmailError("Google did not share an email address.")
    return body


def upsert_google_user(conn, email: str, name: str) -> int:
    email = email.lower()
    now = datetime.now(timezone.utc).isoformat()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row is not None:
        conn.execute(
            "UPDATE users SET name = ?, last_seen_at = ? WHERE id = ?",
            (name or email, now, row["id"]),
        )
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO users (name, email, last_seen_at) VALUES (?, ?, ?)",
        (name or email, email, now),
    )
    return int(cursor.lastrowid)


def take_top_event(conn, client: GmailClient, user_id: int, now: datetime):
    """Keep a single upcoming event: the newest inbox message that has one."""
    for message_id in client.list_ids("in:inbox newer_than:45d", limit=8):
        message = client.get_message(message_id)
        payload = message.get("payload") or {}
        sender_name, _sender_email = parse_from(header(payload.get("headers"), "From"))
        received_ms = message.get("internalDate")
        if received_ms:
            received = datetime.fromtimestamp(int(received_ms) / 1000, tz=timezone.utc)
        else:
            received = now
        drafts = drafts_from_message(message, received, sender_name)
        upcoming = [item for item in drafts if is_upcoming(item.get("starts_at"), now)]
        if not upcoming:
            continue
        drafted = upcoming[0]
        external_id = f"gmail-top:{user_id}"
        starts = as_utc(drafted.get("starts_at"))
        ends = as_utc(drafted.get("ends_at"))
        conn.execute("DELETE FROM events WHERE external_id = ?", (external_id,))
        conn.execute(
            """
            INSERT INTO events (
                account_id, name, tagline, description, starts_at, ends_at,
                location_name, organizer_name, organizer_type, instagram_url,
                partiful_url, created_at, external_id, owner_user_id
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, 'person', '', ?, ?, ?, ?)
            """,
            (
                drafted["name"][:120],
                drafted.get("tagline"),
                drafted.get("description"),
                starts.isoformat() if starts else None,
                ends.isoformat() if ends else None,
                drafted.get("location_name") or "New Haven",
                (sender_name or "Gmail")[:120],
                drafted.get("partiful_url"),
                now.isoformat(),
                external_id,
                user_id,
            ),
        )
        return conn.execute(
            "SELECT * FROM events WHERE external_id = ?",
            (external_id,),
        ).fetchone()
    return None


def profile_email(access_token: str) -> str:
    response = httpx.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=25,
    )
    if response.status_code >= 400:
        return ""
    return response.json().get("emailAddress") or ""


def refresh_access_token(refresh_token: str) -> str:
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=25,
    )
    body = response.json()
    if response.status_code >= 400 or "access_token" not in body:
        raise GmailError(body.get("error_description") or "Gmail refused the refresh token.")
    return body["access_token"]


def gmail_credentials(conn):
    return conn.execute(
        "SELECT * FROM oauth_credentials WHERE provider = 'gmail'"
    ).fetchone()


def client_from_store(conn) -> GmailClient | None:
    row = gmail_credentials(conn)
    if row is None or not row["refresh_token"]:
        return None
    if not os.environ.get("GOOGLE_CLIENT_ID") or not os.environ.get("GOOGLE_CLIENT_SECRET"):
        return None
    return GmailClient(refresh_access_token(row["refresh_token"]))


def _fresh(last_checked_at: str | None, now: datetime, force: bool) -> bool:
    if force or not last_checked_at:
        return False
    try:
        checked = datetime.fromisoformat(last_checked_at)
    except ValueError:
        return False
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    return (now - checked).total_seconds() < STALE_MINUTES * 60


def sync_gmail(conn, client: GmailClient | None, *, force: bool = False, now: datetime | None = None) -> dict:
    """Scan the inbox. Past events are ignored. Senders become profiles."""
    now = now or datetime.now(timezone.utc)
    creds = gmail_credentials(conn)
    if creds is not None and _fresh(creds["last_checked_at"], now, force):
        return {
            "username": "gmail",
            "status": "ok",
            "new_posts": 0,
            "new_events": 0,
            "detail": creds["status_detail"] or "Gmail was checked a few minutes ago.",
        }
    if client is None:
        detail = (
            "Connect Gmail to read invites that have not happened yet. "
            "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET, then use Connect Gmail."
        )
        if creds is not None and creds["refresh_token"] and not os.environ.get("GOOGLE_CLIENT_ID"):
            detail = "Gmail is connected, but GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are missing."
        return {
            "username": "gmail",
            "status": "needs_google",
            "new_posts": 0,
            "new_events": 0,
            "detail": detail,
        }
    try:
        ids = client.list_ids()
        created = 0
        for message_id in ids:
            created += ingest_message(conn, client.get_message(message_id), now)
    except GmailError as error:
        conn.execute(
            """
            INSERT INTO oauth_credentials (provider, refresh_token, email, last_checked_at, status_detail)
            VALUES ('gmail', COALESCE((SELECT refresh_token FROM oauth_credentials WHERE provider = 'gmail'), ''), '', ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                last_checked_at = excluded.last_checked_at,
                status_detail = excluded.status_detail
            """,
            (now.isoformat(), error.message),
        )
        conn.commit()
        return {
            "username": "gmail",
            "status": "error",
            "new_posts": 0,
            "new_events": 0,
            "detail": error.message,
        }
    detail = f"Gmail check put {created} upcoming events on the sheet."
    conn.execute(
        """
        UPDATE oauth_credentials
        SET last_checked_at = ?, status_detail = ?
        WHERE provider = 'gmail'
        """,
        (now.isoformat(), detail),
    )
    conn.commit()
    return {
        "username": "gmail",
        "status": "ok",
        "new_posts": len(ids),
        "new_events": created,
        "detail": detail,
    }
