"""
Comprehensive Test Suite for Beer Club
Tests database integrity, anti-spoiler masking, 0.25 rating increments,
late arrivals, analytics, superlatives calculations, and live HTTP APIs.
"""

import unittest
import os
import time
import json
import urllib.request
import urllib.error
import threading
import sqlite3

import db
import qrcode_gen
import server

TEST_PORT = 8999

class TestBeerClub(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Use a fresh test database
        db.DB_FILE = "test_beerclub.db"
        if os.path.exists(db.DB_FILE):
            os.remove(db.DB_FILE)
        db.init_db()
        db.seed_sample_event()

        # Start background test HTTP server
        cls.server_address = ('127.0.0.1', TEST_PORT)
        cls.httpd = server.ThreadingHTTPServer(cls.server_address, server.BeerClubHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        if os.path.exists("test_beerclub.db"):
            os.remove("test_beerclub.db")

    # 1. Database & Event Creation
    def test_01_event_and_beer_management(self):
        event_id = db.create_event(
            title="Belgian Ale Night",
            theme="Dubbels & Tripels",
            date="2026-11-01",
            beers_data=[
                {"name": "Chimay Blue", "brewery": "Bières de Chimay", "style": "Belgian Strong Dark", "abv": 9.0},
                {"name": "Westmalle Tripel", "brewery": "Brouwerij der Trappisten van Westmalle", "style": "Tripel", "abv": 9.5}
            ]
        )
        self.assertIsNotNone(event_id)
        ev = db.get_event(event_id)
        self.assertEqual(ev["title"], "Belgian Ale Night")
        self.assertEqual(ev["status"], "active")

        beers = db.get_beers(event_id)
        self.assertEqual(len(beers), 2)
        self.assertEqual(beers[0]["name"], "Chimay Blue")

        # Add a 3rd beer
        new_beer_id = db.add_beer(event_id, "Duvel", "Duvel Moortgat", "Belgian Strong Blonde", 8.5)
        beers = db.get_beers(event_id)
        self.assertEqual(len(beers), 3)
        self.assertEqual(beers[2]["name"], "Duvel")
        self.assertEqual(beers[2]["order_num"], 3)

        # Delete a beer and verify re-ordering
        db.delete_beer(beers[1]["id"])
        beers_after = db.get_beers(event_id)
        self.assertEqual(len(beers_after), 2)
        self.assertEqual(beers_after[0]["order_num"], 1)
        self.assertEqual(beers_after[1]["order_num"], 2)
        self.assertEqual(beers_after[1]["name"], "Duvel")

    # 2. Anti-Spoiler Security
    def test_02_anti_spoiler_masking(self):
        event_id = "craft-showdown"
        p = db.join_or_get_participant(event_id, "Charlie", "🦁")

        # Verify status is active (blind tasting)
        db.set_event_status(event_id, "active")
        blind_state = db.get_participant_state(event_id, p["id"])
        
        self.assertFalse(blind_state["is_revealed"])
        for b in blind_state["beers"]:
            self.assertTrue(b["name"].startswith("Beer #"), f"Leaked beer name: {b['name']}")
            self.assertEqual(b["brewery"], "??? (Hidden)", "Leaked brewery")
            self.assertEqual(b["image_url"], "", "Leaked image url")
            self.assertEqual(b["notes"], "", "Leaked notes")

        # Host view MUST see the real beer names
        host_state = db.get_host_state(event_id)
        self.assertEqual(host_state["beers"][0]["name"], "Oktoberfest Märzen")

        # Reveal the event
        db.set_event_status(event_id, "revealed")
        revealed_state = db.get_participant_state(event_id, p["id"])
        self.assertTrue(revealed_state["is_revealed"])
        self.assertEqual(revealed_state["beers"][0]["name"], "Oktoberfest Märzen")
        self.assertEqual(revealed_state["beers"][0]["brewery"], "Paulaner Brauerei")

    # 3. 0.25 Increment Rating Validation
    def test_03_rating_increments_and_rounding(self):
        event_id = "craft-showdown"
        beers = db.get_beers(event_id)
        p = db.join_or_get_participant(event_id, "Diana", "🌾")

        # Exact 0.25 increment
        r1 = db.submit_rating(event_id, beers[0]["id"], p["id"], 4.25)
        self.assertEqual(r1["rating"], 4.25)

        # Off-increment should round to nearest 0.25 (e.g. 3.38 -> 3.50)
        r2 = db.submit_rating(event_id, beers[1]["id"], p["id"], 3.38)
        self.assertEqual(r2["rating"], 3.50)

        # Clamping bounds: 0.5 -> 1.00, 5.8 -> 5.00
        r3 = db.submit_rating(event_id, beers[2]["id"], p["id"], 0.5)
        self.assertEqual(r3["rating"], 1.00)

        r4 = db.submit_rating(event_id, beers[3]["id"], p["id"], 5.8)
        self.assertEqual(r4["rating"], 5.00)

    # 4. Late Arrivals & Missed Beers
    def test_04_late_arrivals_and_retroactive_ratings(self):
        event_id = "craft-showdown"
        db.update_event_round(event_id, 3) # Room is at Beer #3

        # Late arrival joins
        late_guest = db.join_or_get_participant(event_id, "Late Larry", "🕶️")
        state = db.get_participant_state(event_id, late_guest["id"])
        self.assertEqual(state["current_round"], 3) # Starts at active room round

        # Late guest rates Round 1 retroactively
        beers = db.get_beers(event_id)
        db.submit_rating(event_id, beers[0]["id"], late_guest["id"], 4.00, ["Crisp"], "Tasted late")

        # Verify rating was saved
        ratings = db.get_participant_ratings(event_id, late_guest["id"])
        self.assertIn(beers[0]["id"], ratings)
        self.assertEqual(ratings[beers[0]["id"]]["rating"], 4.00)
        self.assertEqual(ratings[beers[0]["id"]]["tags"], ["Crisp"])

    # 5. Superlatives & Analytics Calculations
    def test_05_analytics_and_superlatives(self):
        event_id = db.create_event(
            title="Superlative Showcase",
            theme="Testing Analytics",
            date="2026-11-01",
            beers_data=[
                {"name": "Champion Stout", "brewery": "Brew A"},
                {"name": "Polarizing Sour", "brewery": "Brew B"},
                {"name": "Bland Lager", "brewery": "Brew C"}
            ]
        )
        beers = db.get_beers(event_id)
        p1 = db.join_or_get_participant(event_id, "Generous George", "☀️")
        p2 = db.join_or_get_participant(event_id, "Critical Clara", "🍷")
        p3 = db.join_or_get_participant(event_id, "Balanced Ben", "🎯")

        # Beer 1: Uniformly loved
        db.submit_rating(event_id, beers[0]["id"], p1["id"], 5.00)
        db.submit_rating(event_id, beers[0]["id"], p2["id"], 4.75)
        db.submit_rating(event_id, beers[0]["id"], p3["id"], 5.00)

        # Beer 2: Polarizing (p1 loved it, p2 hated it)
        db.submit_rating(event_id, beers[1]["id"], p1["id"], 5.00)
        db.submit_rating(event_id, beers[1]["id"], p2["id"], 1.00)
        db.submit_rating(event_id, beers[1]["id"], p3["id"], 3.00)

        # Beer 3: Uniformly disliked
        db.submit_rating(event_id, beers[2]["id"], p1["id"], 2.25)
        db.submit_rating(event_id, beers[2]["id"], p2["id"], 1.00)
        db.submit_rating(event_id, beers[2]["id"], p3["id"], 1.50)

        analytics = db.compute_event_analytics(event_id)
        superlatives = analytics["superlatives"]

        # Check Champion
        self.assertEqual(superlatives["champion"]["name"], "Champion Stout")
        # Check Wooden Spoon
        self.assertEqual(superlatives["wooden_spoon"]["name"], "Bland Lager")
        # Check Polarizer
        self.assertEqual(superlatives["polarizer"]["name"], "Polarizing Sour")
        # Check Toughest Critic
        self.assertEqual(superlatives["toughest_critic"]["name"], "Critical Clara")
        # Check Generous Soul
        self.assertEqual(superlatives["generous_soul"]["name"], "Generous George")

        # Check Histogram for Beer 1 (scores: 4.75 and 5.00)
        b1_hist = analytics["beer_stats"][beers[0]["id"]]["histogram"]
        self.assertEqual(b1_hist["5.0"], 2)
        self.assertEqual(b1_hist["4.75"], 1)
        self.assertEqual(b1_hist["1.0"], 0)

    # 6. HTTP API Server Integration
    def test_06_http_api_endpoints(self):
        base_url = f"http://127.0.0.1:{TEST_PORT}"

        # Test /api/info
        with urllib.request.urlopen(f"{base_url}/api/info") as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode())
            self.assertIn("lan_ip", data)

        # Test /api/qrcode
        with urllib.request.urlopen(f"{base_url}/api/qrcode?text=http://test-link") as res:
            self.assertEqual(res.status, 200)
            self.assertEqual(res.headers.get("Content-Type"), "image/svg+xml")
            svg_content = res.read().decode()
            self.assertTrue(svg_content.startswith("<svg"))

        # Test participant join via POST
        join_payload = json.dumps({"name": "API Tester", "avatar": "🍻"}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/events/craft-showdown/join",
            data=join_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)
            join_data = json.loads(res.read().decode())
            self.assertIn("participant", join_data)
            p_id = join_data["participant"]["id"]

        # Test submit rating via POST
        beers = db.get_beers("craft-showdown")
        rate_payload = json.dumps({
            "participant_id": p_id,
            "beer_id": beers[0]["id"],
            "rating": 4.5,
            "tags": ["Piney"]
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/events/craft-showdown/rate",
            data=rate_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)
            rate_data = json.loads(res.read().decode())
            self.assertEqual(rate_data["rating"]["rating"], 4.5)

        # Test update round via POST
        round_payload = json.dumps({"current_beer_index": 2}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/events/craft-showdown/round",
            data=round_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)
            round_data = json.loads(res.read().decode())
            self.assertEqual(round_data["current_beer_index"], 2)

    # 7. Deleting a beer that already has ratings must not raise KeyError
    def test_07_delete_rated_beer_no_keyerror(self):
        event_id = db.create_event(
            title="Deletion Resilience Test",
            theme="Cascade Check",
            date="2026-11-01",
            beers_data=[
                {"name": "Beer One", "brewery": "Brew 1"},
                {"name": "Beer Two", "brewery": "Brew 2"}
            ]
        )
        beers = db.get_beers(event_id)
        p1 = db.join_or_get_participant(event_id, "Taster 1", "🍺")
        p2 = db.join_or_get_participant(event_id, "Taster 2", "🍻")

        db.submit_rating(event_id, beers[0]["id"], p1["id"], 4.0)
        db.submit_rating(event_id, beers[1]["id"], p1["id"], 3.5)
        db.submit_rating(event_id, beers[0]["id"], p2["id"], 4.5)
        db.submit_rating(event_id, beers[1]["id"], p2["id"], 2.5)

        # Delete Beer One after ratings exist, then reveal and fetch states
        db.delete_beer(beers[0]["id"])
        db.set_event_status(event_id, "revealed")

        p_state = db.get_participant_state(event_id, p1["id"])
        h_state = db.get_host_state(event_id)
        self.assertEqual(len(p_state["beers"]), 1)
        self.assertEqual(len(h_state["beers"]), 1)
        self.assertIn("analytics", p_state)

    # 8. Simple Routes (/, /join, /host) and Tab Titles
    def test_08_simple_routes_and_titles(self):
        base_url = f"http://127.0.0.1:{TEST_PORT}"
        db.seed_sample_event(force_reset=True, event_id="craft-showdown")

        # Root '/' and '/join' both serve Participant view with title "Beer Club — Participant"
        for route in ("/", "/join"):
            with urllib.request.urlopen(f"{base_url}{route}") as res:
                self.assertEqual(res.status, 200)
                html = res.read().decode()
                self.assertIn("<title>Beer Club — Participant</title>", html)

        # '/host' serves Host view with title "Beer Club — Host"
        with urllib.request.urlopen(f"{base_url}/host") as res:
            self.assertEqual(res.status, 200)
            html = res.read().decode()
            self.assertIn("<title>Beer Club — Host</title>", html)
            self.assertIn('id="btn-share-join-url"', html)

if __name__ == "__main__":
    unittest.main()
