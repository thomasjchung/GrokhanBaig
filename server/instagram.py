"""Poll professional Instagram accounts through Business Discovery.

A watched account is a username on our list. One app-owned professional token
does every lookup. Personal accounts fail the lookup and stay off the monitor.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .extract import grok_extract, parse_caption

ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = ROOT / "data" / "media"
USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")
STALE_MINUTES = 15


class GraphError(Exception):
    def __init__(self, code: int | None, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def valid_username(username: str) -> bool:
    return bool(USERNAME.fullmatch(username or ""))


def select_new_media(items: list[dict], last_media_id: str | None) -> list[dict]:
    """Items are newest first. Stop at the post we already stored."""
    fresh = []
    for item in items:
        if last_media_id and str(item.get("id")) == str(last_media_id):
            break
        fresh.append(item)
    return fresh


def parse_discovery(payload: dict) -> tuple[dict, list[dict]]:
    discovery = payload.get("business_discovery") or {}
    media = (discovery.get("media") or {}).get("data") or []
    profile = {
        "instagram_user_id": discovery.get("id"),
        "display_name": discovery.get("name"),
        "bio": discovery.get("biography"),
        "website": discovery.get("website"),
    }
    return profile, media


def _image_url(item: dict) -> str | None:
    if item.get("media_url") and item.get("media_type") != "VIDEO":
        return item["media_url"]
    if item.get("thumbnail_url"):
        return item["thumbnail_url"]
    children = (item.get("children") or {}).get("data") or []
    for child in children:
        if child.get("media_url"):
            return child["media_url"]
        if child.get("thumbnail_url"):
            return child["thumbnail_url"]
    return None


class GraphClient:
    def __init__(self, user_id: str, token: str, version: str = "v21.0"):
        self.user_id = user_id
        self.token = token
        self.version = version

    def discover(self, username: str) -> dict:
        if not valid_username(username):
            raise GraphError(None, "Username has characters Instagram will not accept.")
        fields = (
            "business_discovery.username("
            + username
            + "){id,name,biography,website,media.limit(12){id,caption,media_type,"
            "permalink,timestamp,media_url,thumbnail_url,"
            "children{id,media_type,media_url,thumbnail_url}}}"
        )
        response = httpx.get(
            f"https://graph.facebook.com/{self.version}/{self.user_id}",
            params={"fields": fields},
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=25,
        )
        body = response.json()
        if response.status_code >= 400 or "error" in body:
            error = body.get("error") or {}
            raise GraphError(error.get("code"), error.get("message") or response.text)
        return body


def client_from_env() -> GraphClient | None:
    user_id = os.environ.get("IG_USER_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not user_id or not token:
        return None
    version = os.environ.get("IG_GRAPH_VERSION", "v21.0").strip() or "v21.0"
    return GraphClient(user_id, token, version)


def _parse_stamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    text = value.replace("Z", "+00:00")
    if re.match(r".*[+-]\d{4}$", text):
        text = text[:-2] + ":" + text[-2:]
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _save_image(url: str, media_id: str) -> str | None:
    try:
        response = httpx.get(url, timeout=25, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    if len(response.content) > 8_000_000:
        return None
    kind = "jpg"
    content_type = response.headers.get("content-type", "")
    if "png" in content_type:
        kind = "png"
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{media_id}.{kind}"
    (MEDIA_DIR / filename).write_bytes(response.content)
    return filename


def _status_for_error(error: GraphError) -> tuple[str, str]:
    if error.code in (110, 100) or "Invalid user id" in error.message:
        return (
            "not_professional",
            "Instagram would not describe this account. Personal accounts cannot be monitored. "
            "A professional account on our side does not change that.",
        )
    if error.code in (10, 190, 200):
        return (
            "error",
            "The Instagram token cannot read other accounts yet. "
            "Business Discovery needs a Facebook Login token from a professional account you control.",
        )
    return ("error", error.message[:280])


def account_is_fresh(last_checked_at: str | None, now: datetime, force: bool) -> bool:
    if force or not last_checked_at:
        return False
    try:
        checked = datetime.fromisoformat(last_checked_at)
    except ValueError:
        return False
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    age = now - checked
    return age.total_seconds() < STALE_MINUTES * 60


def sync_account(conn, account, graph: GraphClient | None, *, force: bool = False, now: datetime | None = None) -> dict:
    """Pull posts newer than the stored cursor and make events from the captions."""
    now = now or datetime.now(timezone.utc)
    username = account["username"]
    if account_is_fresh(account["last_checked_at"], now, force):
        return {
            "username": username,
            "status": account["status"],
            "new_posts": 0,
            "new_events": 0,
            "detail": account["status_detail"]
            or "Checked a few minutes ago. Using the posts already stored.",
        }
    stamp = now.isoformat()
    if graph is None:
        conn.execute(
            """
            UPDATE accounts
            SET last_checked_at = ?, status = 'needs_api_token',
                status_detail = ?
            WHERE id = ?
            """,
            (
                stamp,
                "Set IG_USER_ID and IG_ACCESS_TOKEN to poll this account. "
                "The token has to come from a professional account on the Facebook Login setup.",
                account["id"],
            ),
        )
        conn.commit()
        return {
            "username": username,
            "status": "needs_api_token",
            "new_posts": 0,
            "new_events": 0,
            "detail": "No Instagram token on this machine, so the new post was not read.",
        }
    try:
        payload = graph.discover(username)
    except GraphError as error:
        status, detail = _status_for_error(error)
        conn.execute(
            """
            UPDATE accounts
            SET last_checked_at = ?, status = ?, status_detail = ?
            WHERE id = ?
            """,
            (stamp, status, detail, account["id"]),
        )
        conn.commit()
        return {
            "username": username,
            "status": status,
            "new_posts": 0,
            "new_events": 0,
            "detail": detail,
        }

    profile, media = parse_discovery(payload)
    fresh = select_new_media(media, account["last_media_id"])
    # API order is newest first. Store oldest of the new batch first so a crash
    # does not skip the older ones on the next cursor move.
    new_posts = 0
    new_events = 0
    newest = media[0] if media else None
    for item in reversed(fresh):
        media_id = str(item.get("id") or "")
        if not media_id:
            continue
        caption = item.get("caption") or ""
        posted = _parse_stamp(item.get("timestamp"))
        image = _image_url(item)
        image_path = _save_image(image, media_id) if image else None
        inserted = conn.execute(
            """
            INSERT OR IGNORE INTO posts (
                account_id, media_id, caption, permalink, media_type, posted_at, image_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account["id"],
                media_id,
                caption,
                item.get("permalink"),
                item.get("media_type"),
                posted.isoformat(),
                image_path,
            ),
        )
        if inserted.rowcount == 0:
            continue
        post_row = conn.execute(
            "SELECT id, image_path FROM posts WHERE account_id = ? AND media_id = ?",
            (account["id"], media_id),
        ).fetchone()
        new_posts += 1
        drafted = None
        if os.environ.get("XAI_API_KEY"):
            try:
                drafted = grok_extract(caption, posted, username)
            except Exception:
                drafted = None
        if drafted is None:
            drafted = parse_caption(caption, posted, username, profile.get("display_name") or account["display_name"])
        if drafted and post_row is not None:
            already = conn.execute(
                "SELECT id FROM events WHERE post_id = ?",
                (post_row["id"],),
            ).fetchone()
            if already is None:
                conn.execute(
                    """
                    INSERT INTO events (
                        account_id, post_id, name, tagline, description, starts_at, ends_at,
                        location_name, image_path, organizer_name, organizer_type,
                        instagram_url, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account["id"],
                        post_row["id"],
                        drafted["name"],
                        drafted.get("tagline"),
                        drafted.get("description"),
                        drafted.get("starts_at"),
                        drafted.get("ends_at"),
                        drafted.get("location_name"),
                        image_path,
                        drafted.get("organizer_name") or account["display_name"],
                        account["organizer_type"] or "club",
                        item.get("permalink") or account["instagram_url"],
                        stamp,
                    ),
                )
                new_events += 1
    cursor_id = str(newest["id"]) if newest else account["last_media_id"]
    cursor_at = newest.get("timestamp") if newest else account["last_media_at"]
    conn.execute(
        """
        UPDATE accounts
        SET instagram_user_id = COALESCE(?, instagram_user_id),
            display_name = COALESCE(?, display_name),
            bio = COALESCE(?, bio),
            website = COALESCE(?, website),
            status = 'ok',
            status_detail = ?,
            last_media_id = ?,
            last_media_at = ?,
            last_checked_at = ?
        WHERE id = ?
        """,
        (
            profile.get("instagram_user_id"),
            profile.get("display_name"),
            profile.get("bio"),
            profile.get("website"),
            f"Last check found {new_posts} new posts.",
            cursor_id,
            cursor_at,
            stamp,
            account["id"],
        ),
    )
    conn.commit()
    return {
        "username": username,
        "status": "ok",
        "new_posts": new_posts,
        "new_events": new_events,
        "detail": f"Checked @{username}. {new_posts} new posts, {new_events} put on the sheet.",
    }
