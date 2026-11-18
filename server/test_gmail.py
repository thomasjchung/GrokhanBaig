"""Gmail grouping: one sender, many upcoming events, nothing from the past."""

from __future__ import annotations

import base64
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


def encoded(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


# A November 2026 receipt, so "December 12" stays in 2026 and is still upcoming.
RECEIVED_MS = str(int(datetime(2026, 11, 16, tzinfo=timezone.utc).timestamp() * 1000))


def message(mid: str, sender: str, subject: str, plain: str = "", ics: str = "") -> dict:
    parts = []
    if plain:
        parts.append({"mimeType": "text/plain", "body": {"data": encoded(plain)}})
    if ics:
        parts.append(
            {
                "mimeType": "text/calendar",
                "filename": "invite.ics",
                "body": {"data": encoded(ics)},
            }
        )
    return {
        "id": mid,
        "internalDate": RECEIVED_MS,
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
            ],
            "parts": parts,
        },
    }


FUTURE_ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:rb-1@partiful
SUMMARY:RBirthday
DTSTART:20261201T230000Z
LOCATION:Off Broadway
DESCRIPTION:Tickets for the anniversary show
END:VEVENT
END:VCALENDAR
"""

SECOND_ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:rb-2@partiful
SUMMARY:Winter Formal
DTSTART:20261205T010000Z
LOCATION:Saybrook
END:VEVENT
END:VCALENDAR
"""

PAST_ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:old@yale
SUMMARY:Old showcase
DTSTART:20261101T230000Z
LOCATION:LC 102
END:VEVENT
END:VCALENDAR
"""


class GmailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SHEET_DB"] = str(Path(self.tmp.name) / "sheet.db")
        os.environ.pop("GOOGLE_CLIENT_ID", None)
        os.environ.pop("GOOGLE_CLIENT_SECRET", None)
        os.environ.pop("XAI_API_KEY", None)
        from server.db import init_db

        init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_sender_shares_one_profile_and_past_mail_is_dropped(self):
        from server.db import connect
        from server.gmail import sync_gmail

        class FakeGmail:
            def list_ids(self):
                return ["a", "b", "c"]

            def get_message(self, message_id):
                return {
                    "a": message("a", "Partiful <invites@partiful.com>", "You're invited", ics=FUTURE_ICS),
                    "b": message("b", "Partiful <invites@partiful.com>", "You're invited", ics=SECOND_ICS),
                    "c": message("c", "Yale Arts <arts@yale.edu>", "Last month", ics=PAST_ICS),
                }[message_id]

        conn = connect()
        now = datetime(2026, 11, 18, tzinfo=timezone.utc)
        first = sync_gmail(conn, FakeGmail(), force=True, now=now)
        self.assertEqual(first["new_events"], 2)
        profiles = conn.execute(
            "SELECT username, display_name, email FROM accounts WHERE provider = 'email'"
        ).fetchall()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["email"], "invites@partiful.com")
        self.assertEqual(profiles[0]["display_name"], "Partiful")
        events = conn.execute(
            "SELECT name, location_name FROM events ORDER BY starts_at"
        ).fetchall()
        self.assertEqual([row["name"] for row in events], ["RBirthday", "Winter Formal"])
        self.assertEqual(events[0]["location_name"], "Off Broadway")
        second = sync_gmail(conn, FakeGmail(), force=True, now=now)
        self.assertEqual(second["new_events"], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"], 2)
        watching = conn.execute(
            """
            SELECT 1 FROM follows
            JOIN accounts ON accounts.id = follows.account_id
            WHERE accounts.email = 'invites@partiful.com'
            """
        ).fetchone()
        conn.close()
        self.assertIsNotNone(watching)

    def test_plain_invite_becomes_an_event(self):
        from server.db import connect
        from server.gmail import ingest_message

        conn = connect()
        created = ingest_message(
            conn,
            message(
                "d",
                "Morse Council <morse@yale.edu>",
                "Morse formal",
                plain="Tickets for Morse Formal. December 12 at 9pm at Morse College.",
            ),
            datetime(2026, 11, 18, tzinfo=timezone.utc),
        )
        conn.commit()
        row = conn.execute("SELECT name, location_name, starts_at FROM events").fetchone()
        conn.close()
        self.assertEqual(created, 1)
        self.assertEqual(row["name"], "Morse Formal")
        self.assertEqual(row["location_name"], "Morse College")
        self.assertTrue(row["starts_at"].startswith("2026-12-13T02:00:00"))

    def test_top_event_keeps_only_the_newest_upcoming_mail(self):
        from server.db import connect
        from server.gmail import take_top_event

        class FakeGmail:
            def list_ids(self, query=None, limit=25):
                return ["new", "older"]

            def get_message(self, message_id):
                if message_id == "new":
                    return message(
                        "new",
                        "Partiful <invites@partiful.com>",
                        "You're invited",
                        ics=FUTURE_ICS,
                    )
                return message(
                    "older",
                    "Yale Arts <arts@yale.edu>",
                    "You're invited",
                    ics=SECOND_ICS,
                )

        conn = connect()
        row = take_top_event(
            conn,
            FakeGmail(),
            user_id=1,
            now=datetime(2026, 11, 18, tzinfo=timezone.utc),
        )
        conn.commit()
        names = [item["name"] for item in conn.execute("SELECT name FROM events").fetchall()]
        conn.close()
        self.assertEqual(row["name"], "RBirthday")
        self.assertEqual(names, ["RBirthday"])

    def test_check_reports_gmail_when_nothing_is_connected(self):
        from fastapi.testclient import TestClient
        from server.main import app

        client = TestClient(app)
        checked = client.post("/api/checks", params={"force": "true"}).json()
        gmail = [item for item in checked["accounts"] if item["username"] == "gmail"]
        self.assertEqual(gmail[0]["status"], "needs_google")
        status = client.get("/api/gmail").json()
        self.assertFalse(status["connected"])
        start = client.get("/api/gmail/start")
        self.assertEqual(start.status_code, 400)


if __name__ == "__main__":
    unittest.main()
