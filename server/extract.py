"""Turn a caption into one event. Rules first. Grok only when a key is set."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

EVENT_WORDS = re.compile(
    r"\b(tickets?|shows?|party|parties|concert|rsvp|doors|performance|showcase|"
    r"tonight|tomorrow|festival|meetup|workshop|audition|premiere|gala)\b",
    re.I,
)
ORDINAL = re.compile(r"(\d+)(st|nd|rd|th)", re.I)
SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
MONTH_DATE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\.?\s+(\d{1,2})\b",
    re.I,
)
TIME_PAIR = re.compile(r"\b(\d{1,2})\s*&\s*(\d{1,2})\s*(am|pm)\b", re.I)
TIME_ONE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.I)
AT_PLACE = re.compile(r"\bat\s+([A-Z][^.,\n]{2,48})")


def looks_like_event(caption: str) -> bool:
    if not caption or not caption.strip():
        return False
    if EVENT_WORDS.search(caption):
        return True
    if SLASH_DATE.search(caption) or MONTH_DATE.search(caption):
        return True
    return False


def _year(posted_at: datetime, month: int, day: int) -> int:
    year = posted_at.year
    try:
        candidate = posted_at.replace(month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        return year
    if candidate < posted_at - timedelta(days=45):
        return year + 1
    return year


def find_dates(caption: str, posted_at: datetime) -> list[datetime]:
    text = ORDINAL.sub(r"\1", caption)
    found: list[datetime] = []
    for match in SLASH_DATE.finditer(text):
        month, day = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else _year(posted_at, month, day)
        if year < 100:
            year += 2000
        if 1 <= month <= 12 and 1 <= day <= 31:
            found.append(datetime(year, month, day))
    for match in MONTH_DATE.finditer(text):
        month = MONTHS[match.group(1).lower()[:3]]
        day = int(match.group(2))
        if 1 <= day <= 31:
            found.append(datetime(_year(posted_at, month, day), month, day))
        extra = re.match(r"\s*(?:st|nd|rd|th)?\s+and\s+(\d{1,2})\b", text[match.end():], re.I)
        if extra:
            extra_day = int(extra.group(1))
            if 1 <= extra_day <= 31:
                found.append(datetime(_year(posted_at, month, extra_day), month, extra_day))
    if re.search(r"\btomorrow\b", text, re.I) and not found:
        nxt = posted_at + timedelta(days=1)
        found.append(datetime(nxt.year, nxt.month, nxt.day))
    # Unique, keep order.
    seen = set()
    unique = []
    for item in found:
        key = item.date()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def find_times(caption: str) -> list[tuple[int, int]]:
    text = ORDINAL.sub(r"\1", caption)
    spans: list[tuple[int, list[tuple[int, int]]]] = []
    for match in TIME_PAIR.finditer(text):
        marker = match.group(3).lower()
        spans.append(
            (
                match.start(),
                [
                    _to_24(int(match.group(1)), 0, marker),
                    _to_24(int(match.group(2)), 0, marker),
                ],
            )
        )
    covered = [match.span() for match in TIME_PAIR.finditer(text)]
    for match in TIME_ONE.finditer(text):
        if any(start <= match.start() < end for start, end in covered):
            continue
        minute = int(match.group(2) or 0)
        spans.append(
            (match.start(), [_to_24(int(match.group(1)), minute, match.group(3).lower())])
        )
    times: list[tuple[int, int]] = []
    for _start, group in sorted(spans, key=lambda item: item[0]):
        times.extend(group)
    return times


def _to_24(hour: int, minute: int, marker: str) -> tuple[int, int]:
    hour = hour % 12
    if marker == "pm":
        hour += 12
    return hour, minute


def _apply_time(day: datetime, times: list[tuple[int, int]], index: int) -> datetime:
    if not times:
        return day.replace(hour=19, minute=0)
    hour, minute = times[min(index, len(times) - 1)]
    return day.replace(hour=hour, minute=minute)


def event_name(caption: str, username: str) -> str:
    cleaned = caption.strip()
    named = re.search(r"tickets?\s+for\s+([^:.\n]{2,60})", cleaned, re.I)
    if named:
        return named.group(1).strip()
    first = re.split(r"[\n.]", cleaned, maxsplit=1)[0].strip()
    if 2 <= len(first) <= 72:
        return first
    return f"Post from @{username}"


def parse_caption(caption: str, posted_at: datetime, username: str, display_name: str) -> dict | None:
    if not looks_like_event(caption):
        return None
    dates = find_dates(caption, posted_at)
    times = find_times(caption)
    # The earlier date is often the ticket drop. The show is the later one.
    show_day = dates[-1] if dates else None
    show_times = times[-2:] if len(dates) > 1 and len(times) > 1 else times
    starts = _apply_time(show_day, show_times, 0) if show_day else None
    ends = None
    if len(show_times) > 1 and starts is not None:
        hour, minute = show_times[-1]
        ends = starts.replace(hour=hour, minute=minute)
        if ends <= starts:
            ends = None
    place = AT_PLACE.search(caption)
    first, _, rest = caption.strip().partition("\n")
    tagline = rest.strip() or None
    if tagline is None and ". " in caption:
        tagline = caption.split(". ", 1)[1].strip()
    return {
        "name": event_name(caption, username),
        "tagline": (tagline or "")[:180] or None,
        "description": caption.strip(),
        "starts_at": starts.isoformat() if starts else None,
        "ends_at": ends.isoformat() if ends else None,
        "location_name": place.group(1).strip() if place else None,
        "organizer_name": display_name,
        "organizer_type": "club",
    }


def grok_extract(caption: str, posted_at: datetime, username: str) -> dict | None:
    """Ask Grok for the same fields. Returns None when the key is missing or the call fails."""
    key = os.environ.get("XAI_API_KEY")
    if not key:
        return None
    import httpx

    prompt = {
        "posted_at": posted_at.isoformat(),
        "username": username,
        "caption": caption,
    }
    response = httpx.post(
        "https://api.x.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "grok-4.7",
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract one campus event from an Instagram caption. "
                        "Resolve words like tomorrow against posted_at. "
                        "Return JSON with is_event (bool), name, tagline, "
                        "starts_at (ISO or null), ends_at, location_name. "
                        "is_event is false when the caption is not an event."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt)},
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    if not data.get("is_event"):
        return None
    return {
        "name": data.get("name") or f"Post from @{username}",
        "tagline": data.get("tagline"),
        "description": caption.strip(),
        "starts_at": data.get("starts_at"),
        "ends_at": data.get("ends_at"),
        "location_name": data.get("location_name"),
        "organizer_name": username,
        "organizer_type": "club",
    }
