"""Checks for the watch list, the cursor, and caption parsing."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SheetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SHEET_DB"] = str(Path(self.tmp.name) / "sheet.db")
        os.environ.pop("IG_USER_ID", None)
        os.environ.pop("IG_ACCESS_TOKEN", None)
        os.environ.pop("XAI_API_KEY", None)
        from server.db import init_db

        init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_directory_has_farhan_and_tommy(self):
        from server.db import connect

        conn = connect()
        row = conn.execute(
            "SELECT * FROM accounts WHERE username = 'farhanandtommyclub'"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["instagram_url"], "https://www.instagram.com/farhanandtommyclub/")
        self.assertIn("farhanandtommyclub", row["instagram_url"])

    def test_search_and_login_check_without_a_token(self):
        from fastapi.testclient import TestClient
        from server.main import app

        client = TestClient(app)
        found = client.get("/api/accounts", params={"q": "farhan"}).json()
        self.assertEqual(found["accounts"][0]["username"], "farhanandtommyclub")
        self.assertTrue(found["accounts"][0]["watching"])
        checked = client.post("/api/checks", params={"force": "true"}).json()
        self.assertEqual(checked["accounts"][0]["status"], "needs_api_token")
        self.assertEqual(checked["accounts"][0]["new_posts"], 0)
        again = client.post("/api/checks").json()
        self.assertEqual(again["accounts"][0]["status"], "needs_api_token")
        self.assertIn("IG_ACCESS_TOKEN", again["accounts"][0]["detail"])

    def test_cursor_ingests_a_new_post_once(self):
        from server.db import connect
        from server.instagram import sync_account

        class FakeGraph:
            def __init__(self):
                self.calls = 0

            def discover(self, username):
                self.calls += 1
                posts = [
                    {
                        "id": "222",
                        "caption": "Tickets for Roof Set drop Friday. Show is November 20 at 9pm at Toad's Place.",
                        "permalink": "https://www.instagram.com/p/NEWPOST/",
                        "timestamp": "2026-11-17T23:40:00+0000",
                        "media_type": "IMAGE",
                    }
                ]
                if self.calls == 1:
                    posts.append(
                        {
                            "id": "111",
                            "caption": "rehearsal notes from Tuesday",
                            "permalink": "https://www.instagram.com/p/OLD/",
                            "timestamp": "2026-11-10T23:40:00+0000",
                            "media_type": "IMAGE",
                        }
                    )
                return {
                    "business_discovery": {
                        "id": "1784",
                        "name": "Farhan and Tommy Club",
                        "biography": "New Haven",
                        "media": {"data": posts},
                    }
                }

        graph = FakeGraph()
        conn = connect()
        account = conn.execute(
            "SELECT * FROM accounts WHERE username = 'farhanandtommyclub'"
        ).fetchone()
        first = sync_account(conn, account, graph, force=True)
        self.assertEqual(first["new_posts"], 2)
        self.assertEqual(first["new_events"], 1)
        account = conn.execute(
            "SELECT * FROM accounts WHERE username = 'farhanandtommyclub'"
        ).fetchone()
        self.assertEqual(account["last_media_id"], "222")
        self.assertEqual(account["instagram_user_id"], "1784")
        second = sync_account(conn, account, graph, force=True)
        self.assertEqual(second["new_posts"], 0)
        events = conn.execute("SELECT name, location_name, starts_at FROM events").fetchall()
        conn.close()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "Roof Set drop Friday")
        self.assertEqual(events[0]["location_name"], "Toad's Place")
        self.assertTrue(events[0]["starts_at"].startswith("2026-11-20T21:00:00"))

    def test_show_caption_uses_the_later_date(self):
        from server.extract import parse_caption

        caption = (
            "The party starts sooner than you think.\n\n"
            "Tickets for RBirthday: Celebrating 35 years of RB will be available "
            "TOMORROW 11/9th @ 5pm. The shows will take place on November 11th and 13th at 6&9pm."
        )
        drafted = parse_caption(
            caption,
            datetime(2026, 11, 8, 18, tzinfo=timezone.utc),
            "rhythmicblue",
            "Rhythmic Blue",
        )
        self.assertEqual(drafted["name"], "RBirthday")
        self.assertTrue(drafted["starts_at"].startswith("2026-11-13T18:00:00"))
        self.assertTrue(drafted["ends_at"].startswith("2026-11-13T21:00:00"))

    def test_plain_caption_is_not_an_event(self):
        from server.extract import parse_caption

        drafted = parse_caption(
            "rehearsal notes from Tuesday",
            datetime(2026, 11, 10, tzinfo=timezone.utc),
            "farhanandtommyclub",
            "Farhan and Tommy Club",
        )
        self.assertIsNone(drafted)

    def test_rsvp_and_manual_event(self):
        from fastapi.testclient import TestClient
        from server.main import app

        client = TestClient(app)
        created = client.post(
            "/api/events",
            json={"name": "Late hall", "location_name": "LC 102", "starts_at": "2026-11-18T22:00:00"},
        ).json()
        self.assertEqual(created["rsvp"]["status"], "none")
        going = client.post(f"/api/events/{created['id']}/rsvp", json={"status": "going"}).json()
        self.assertEqual(going["rsvp"]["going_count"], 1)
        listed = client.get("/api/events").json()
        self.assertEqual(listed["events"][0]["name"], "Late hall")


if __name__ == "__main__":
    unittest.main()
