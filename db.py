"""
Database schema, operations, and analytics engine for Beer Club.
Uses Python sqlite3 with JSON and math utilities.
"""

import sqlite3
import json
import uuid
import math
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_FILE = "beerclub.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                theme TEXT,
                date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active', -- 'setup', 'active', 'revealed'
                current_beer_index INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS beers (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                order_num INTEGER NOT NULL,
                name TEXT NOT NULL,
                brewery TEXT NOT NULL,
                style TEXT,
                abv REAL,
                image_url TEXT,
                notes TEXT,
                FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                name TEXT NOT NULL,
                avatar TEXT NOT NULL DEFAULT '🍺',
                joined_at TEXT NOT NULL,
                last_active_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                beer_id TEXT NOT NULL,
                participant_id TEXT NOT NULL,
                rating REAL NOT NULL,
                tags TEXT, -- JSON array of tags, e.g. ["Citrusy", "Hoppy"]
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(event_id, beer_id, participant_id),
                FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                FOREIGN KEY (beer_id) REFERENCES beers (id) ON DELETE CASCADE,
                FOREIGN KEY (participant_id) REFERENCES participants (id) ON DELETE CASCADE
            );
        """)
        # Clean up any legacy orphaned ratings from before foreign_keys pragma was enabled
        conn.execute("DELETE FROM ratings WHERE beer_id NOT IN (SELECT id FROM beers);")
    conn.close()

DEFAULT_SAMPLE_BEERS = [
    (
        1,
        "Oktoberfest Märzen",
        "Paulaner Brauerei",
        "Märzen / German Amber Lager",
        5.8,
        "https://www.totalwine.com/dynamic/x1000,12pk/images/12229127/12229127-2-fr.png",
        "Deep amber pour with rich toasted bread crust, soft caramel malt, and a smooth, incredibly clean German lager finish."
    ),
    (
        2,
        "Oktoberfest",
        "Sierra Nevada Brewing Co.",
        "Festive Festbier / Märzen",
        6.0,
        "https://norfolkwineandspirits.com/wp-content/uploads/2020/08/sierra-nevada-oktoberfest-12-oz-bottled-890x890-1.jpg",
        "Golden-amber, featuring toasted biscuit malts, a subtle floral-herbal hop aroma, and a crisp, dry autumn finish."
    ),
    (
        3,
        "Pumking",
        "Southern Tier Brewing Company",
        "Imperial Pumpkin Ale",
        8.6,
        "https://stbcbeer.com/wp-content/uploads/2019/08/STBC_Pumking_2023_12oz-Bottle_Render_face.png",
        "Pours golden copper with bold aromas of fresh pumpkin pie crust, nutmeg, cinnamon, vanilla, and buttery brown sugar."
    ),
    (
        4,
        "Night Owl Pumpkin Ale",
        "Elysian Brewing Company",
        "Pumpkin Ale",
        6.7,
        "https://halftimebeverage.com/media/catalog/product/cache/f3020b7489dcfc4d1d147cf4dad07b7f/1/0/10243_1.png",
        "Brewed with real pumpkin seeds and flesh; layered with cinnamon, nutmeg, clove, and a sweet, toasted malt body."
    ),
    (
        5,
        "Nosferatu",
        "Great Lakes Brewing Co.",
        "Imperial Red Ale",
        9.0,
        "https://thefullpint.com/wp-content/uploads/2009/10/Nosferatu_BottleGlass.jpg",
        "Ruby-red body with massive roasted caramel malt sweetness balanced by a sharp, piney, resinous hop bitterness ideal for cool fall nights."
    ),
    (
        6,
        "Celebrator",
        "Brauerei Aying",
        "Doppelbock",
        6.7,
        "https://halftimebeverage.com/media/catalog/product/cache/f3020b7489dcfc4d1d147cf4dad07b7f/4/4/4415.png",
        "Dark brown with mahogany highlights. Flavors of dark dried fruit (figs, raisins), toasted rye bread, dark chocolate, and warming malt complexity."
    ),
]

def seed_sample_event(force_reset: bool = False, event_id: str = "craft-showdown"):
    """Seeds the default 'Fall Brews' sample event if no events exist yet (or if force_reset=True)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as count FROM events")
    should_seed = force_reset or (cur.fetchone()["count"] == 0)
    if should_seed:
        now = datetime.now().isoformat()
        today = datetime.now().strftime("%Y-%m-%d")
        with conn:
            conn.execute("DELETE FROM ratings WHERE event_id = ?", (event_id,))
            conn.execute("DELETE FROM participants WHERE event_id = ?", (event_id,))
            conn.execute("DELETE FROM beers WHERE event_id = ?", (event_id,))
            conn.execute("""
                INSERT INTO events (id, title, theme, date, status, current_beer_index, created_at)
                VALUES (?, ?, ?, ?, 'active', 1, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    theme = excluded.theme,
                    date = excluded.date,
                    status = 'active',
                    current_beer_index = 1
            """, (
                event_id,
                "Fall Brews",
                "Autumnal Themed Beer Flight",
                today,
                now
            ))

            rows = [
                (str(uuid.uuid4()), event_id, order_num, name, brewery, style, abv, image_url, notes)
                for (order_num, name, brewery, style, abv, image_url, notes) in DEFAULT_SAMPLE_BEERS
            ]
            conn.executemany("""
                INSERT INTO beers (id, event_id, order_num, name, brewery, style, abv, image_url, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
    conn.close()

# ----------------- Events -----------------

def get_event(event_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def list_events() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_event(title: str, theme: str, date: str, beers_data: List[Dict[str, Any]]) -> str:
    event_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO events (id, title, theme, date, status, current_beer_index, created_at)
            VALUES (?, ?, ?, ?, 'active', 1, ?)
        """, (event_id, title, theme, date, now))

        for idx, b in enumerate(beers_data, start=1):
            beer_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO beers (id, event_id, order_num, name, brewery, style, abv, image_url, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                beer_id,
                event_id,
                idx,
                b.get("name", f"Beer #{idx}"),
                b.get("brewery", "Unknown Brewery"),
                b.get("style", ""),
                float(b.get("abv", 0.0) or 0.0),
                b.get("image_url", ""),
                b.get("notes", "")
            ))
    conn.close()
    return event_id

def update_event_round(event_id: str, current_beer_index: int):
    conn = get_connection()
    with conn:
        conn.execute("""
            UPDATE events SET current_beer_index = ? WHERE id = ?
        """, (current_beer_index, event_id))
    conn.close()

def set_event_status(event_id: str, status: str):
    conn = get_connection()
    with conn:
        conn.execute("""
            UPDATE events SET status = ? WHERE id = ?
        """, (status, event_id))
    conn.close()

def update_event_details(event_id: str, title: str, theme: str, date: str):
    conn = get_connection()
    with conn:
        conn.execute("""
            UPDATE events SET title = ?, theme = ?, date = ? WHERE id = ?
        """, (title.strip(), theme.strip(), date.strip(), event_id))
    conn.close()

def reset_event_blank(event_id: str = "craft-showdown"):
    """Wipes all beers, participants, and ratings for the event to start completely fresh."""
    now = datetime.now().isoformat()
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM ratings WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM participants WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM beers WHERE event_id = ?", (event_id,))
        conn.execute("""
            INSERT INTO events (id, title, theme, date, status, current_beer_index, created_at)
            VALUES (?, 'New Beer Club Event', '', ?, 'active', 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = 'New Beer Club Event',
                theme = '',
                date = excluded.date,
                status = 'active',
                current_beer_index = 1
        """, (event_id, today, now))
    conn.close()

# ----------------- Beers -----------------

def get_beers(event_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM beers WHERE event_id = ? ORDER BY order_num ASC", (event_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_beer(event_id: str, name: str, brewery: str, style: str = "", abv: float = 0.0, image_url: str = "", notes: str = "") -> str:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(order_num), 0) + 1 as next_order FROM beers WHERE event_id = ?", (event_id,))
        next_order = cur.fetchone()["next_order"]
        beer_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO beers (id, event_id, order_num, name, brewery, style, abv, image_url, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (beer_id, event_id, next_order, name, brewery, style, abv, image_url, notes))
    conn.close()
    return beer_id

def delete_beer(beer_id: str):
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT event_id, order_num FROM beers WHERE id = ?", (beer_id,))
        row = cur.fetchone()
        if row:
            event_id = row["event_id"]
            cur.execute("DELETE FROM ratings WHERE beer_id = ?", (beer_id,))
            cur.execute("DELETE FROM beers WHERE id = ?", (beer_id,))
            # Reorder remaining beers
            cur.execute("SELECT id FROM beers WHERE event_id = ? ORDER BY order_num ASC", (event_id,))
            remaining = cur.fetchall()
            for idx, r in enumerate(remaining, start=1):
                cur.execute("UPDATE beers SET order_num = ? WHERE id = ?", (idx, r["id"]))
            # Clamp current_beer_index so it never exceeds remaining beer count
            max_round = max(1, len(remaining))
            cur.execute("UPDATE events SET current_beer_index = MIN(current_beer_index, ?) WHERE id = ?", (max_round, event_id))
    conn.close()

def move_beer(beer_id: str, direction: str):
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT id, event_id, order_num FROM beers WHERE id = ?", (beer_id,))
        row = cur.fetchone()
        if row:
            event_id = row["event_id"]
            curr_order = row["order_num"]
            target_order = curr_order - 1 if direction == "up" else curr_order + 1
            cur.execute("SELECT id FROM beers WHERE event_id = ? AND order_num = ?", (event_id, target_order))
            neighbor = cur.fetchone()
            if neighbor:
                cur.execute("UPDATE beers SET order_num = ? WHERE id = ?", (curr_order, neighbor["id"]))
                cur.execute("UPDATE beers SET order_num = ? WHERE id = ?", (target_order, beer_id))
    conn.close()

# ----------------- Participants -----------------

def join_or_get_participant(event_id: str, name: str, avatar: str = "🍺", participant_id: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection()
    now = datetime.now().isoformat()
    with conn:
        cur = conn.cursor()
        if participant_id:
            cur.execute("SELECT * FROM participants WHERE id = ? AND event_id = ?", (participant_id, event_id))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE participants SET name = ?, avatar = ?, last_active_at = ? WHERE id = ?", (name, avatar, now, participant_id))
                return dict(row)

        new_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO participants (id, event_id, name, avatar, joined_at, last_active_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (new_id, event_id, name.strip(), avatar, now, now))
        cur.execute("SELECT * FROM participants WHERE id = ?", (new_id,))
        p = dict(cur.fetchone())
    conn.close()
    return p

def get_participants(event_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM participants WHERE event_id = ? ORDER BY joined_at ASC", (event_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ----------------- Ratings -----------------

def submit_rating(event_id: str, beer_id: str, participant_id: str, rating: float, tags: List[str] = None, notes: str = "") -> Dict[str, Any]:
    # Round rating to nearest 0.25 between 1.0 and 5.0
    val = round(float(rating) * 4) / 4
    val = max(1.0, min(5.0, val))

    tags_json = json.dumps(tags or [])
    now = datetime.now().isoformat()
    rating_id = str(uuid.uuid4())

    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ratings (id, event_id, beer_id, participant_id, rating, tags, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id, beer_id, participant_id) DO UPDATE SET
                rating = excluded.rating,
                tags = excluded.tags,
                notes = excluded.notes,
                updated_at = excluded.updated_at
        """, (rating_id, event_id, beer_id, participant_id, val, tags_json, notes, now, now))

        cur.execute("""
            SELECT * FROM ratings WHERE event_id = ? AND beer_id = ? AND participant_id = ?
        """, (event_id, beer_id, participant_id))
        result = dict(cur.fetchone())
        result["tags"] = json.loads(result["tags"]) if result["tags"] else []
    conn.close()
    return result

def get_event_ratings(event_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.*, p.name as participant_name, p.avatar as participant_avatar
        FROM ratings r
        JOIN participants p ON r.participant_id = p.id
        JOIN beers b ON r.beer_id = b.id
        WHERE r.event_id = ?
    """, (event_id,))
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        results.append(d)
    return results

def get_participant_ratings(event_id: str, participant_id: str) -> Dict[str, Any]:
    """Returns a map of beer_id -> rating data for a single participant."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.* FROM ratings r
        JOIN beers b ON r.beer_id = b.id
        WHERE r.event_id = ? AND r.participant_id = ?
    """, (event_id, participant_id))
    rows = cur.fetchall()
    conn.close()
    out = {}
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        out[d["beer_id"]] = d
    return out

# ----------------- State & Anti-Spoiler Logic -----------------

def get_participant_state(event_id: str, participant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    event = get_event(event_id)
    if not event:
        return None

    beers = get_beers(event_id)
    is_revealed = (event["status"] == "revealed")

    # Anti-spoiler transformation: Hide beer names, breweries, photos unless revealed
    sanitized_beers = []
    for b in beers:
        if is_revealed:
            sanitized_beers.append(b)
        else:
            sanitized_beers.append({
                "id": b["id"],
                "event_id": b["event_id"],
                "order_num": b["order_num"],
                "name": f"Beer #{b['order_num']}",
                "brewery": "??? (Hidden)",
                "style": "Blind Tasting",
                "abv": None,
                "image_url": "",
                "notes": ""
            })

    my_ratings = get_participant_ratings(event_id, participant_id) if participant_id else {}
    participants = get_participants(event_id)
    all_ratings = get_event_ratings(event_id)
    participant_registered = any(p["id"] == participant_id for p in participants) if participant_id else False

    # Build round_statuses: beer_id -> list of participant status dicts
    # Numeric ratings of peers are only included once this participant has rated that beer (or event is revealed)
    ratings_by_beer: Dict[str, Dict[str, Any]] = {b["id"]: {} for b in beers}
    for r in all_ratings:
        if r["beer_id"] in ratings_by_beer:
            ratings_by_beer[r["beer_id"]][r["participant_id"]] = r["rating"]

    round_statuses: Dict[str, List[Dict[str, Any]]] = {}
    for b in beers:
        b_id = b["id"]
        has_i_rated = b_id in my_ratings
        b_map = ratings_by_beer.get(b_id, {})
        statuses = []
        for p in participants:
            p_has_rated = p["id"] in b_map
            statuses.append({
                "id": p["id"],
                "name": p["name"],
                "avatar": p["avatar"],
                "has_rated": p_has_rated,
                "rating": b_map[p["id"]] if (p_has_rated and (has_i_rated or is_revealed)) else None
            })
        round_statuses[b_id] = statuses

    state = {
        "event": event,
        "beers": sanitized_beers,
        "is_revealed": is_revealed,
        "current_round": event["current_beer_index"],
        "total_beers": len(beers),
        "my_ratings": my_ratings,
        "round_statuses": round_statuses,
        "participant_registered": participant_registered
    }

    if is_revealed:
        analytics = compute_event_analytics(event_id)
        state["analytics"] = analytics

    return state

def get_host_state(event_id: str) -> Optional[Dict[str, Any]]:
    event = get_event(event_id)
    if not event:
        return None

    beers = get_beers(event_id)
    participants = get_participants(event_id)
    ratings = get_event_ratings(event_id)
    analytics = compute_event_analytics(event_id)

    # Build matrix of beer ratings by participant
    # beer_id -> { participant_id -> rating }
    ratings_by_beer: Dict[str, Dict[str, Any]] = {b["id"]: {} for b in beers}
    for r in ratings:
        if r["beer_id"] in ratings_by_beer:
            ratings_by_beer[r["beer_id"]][r["participant_id"]] = {
                "rating": r["rating"],
                "tags": r["tags"],
                "notes": r["notes"]
            }

    # Status of current round: who rated and who hasn't
    curr_beer_order = event["current_beer_index"]
    current_beer = next((b for b in beers if b["order_num"] == curr_beer_order), None)
    current_beer_ratings = ratings_by_beer.get(current_beer["id"], {}) if current_beer else {}

    participant_statuses = []
    for p in participants:
        has_rated = p["id"] in current_beer_ratings
        participant_statuses.append({
            "id": p["id"],
            "name": p["name"],
            "avatar": p["avatar"],
            "has_rated": has_rated,
            "rating": current_beer_ratings.get(p["id"], {}).get("rating") if has_rated else None,
            "notes": current_beer_ratings.get(p["id"], {}).get("notes", "") if has_rated else ""
        })

    return {
        "event": event,
        "beers": beers,
        "participants": participants,
        "participant_statuses": participant_statuses,
        "ratings_count": len(ratings),
        "analytics": analytics
    }

# ----------------- Analytics, Histograms & Superlatives -----------------

def compute_event_analytics(event_id: str) -> Dict[str, Any]:
    beers = get_beers(event_id)
    participants = get_participants(event_id)
    ratings = get_event_ratings(event_id)

    # 1. Histogram bins: 1.00 to 5.00 in 0.25 steps (17 bins)
    possible_ratings = [round(1.0 + i * 0.25, 2) for i in range(17)]

    beer_stats: Dict[str, Any] = {}
    for b in beers:
        b_id = b["id"]
        b_ratings = [r["rating"] for r in ratings if r["beer_id"] == b_id]
        
        hist = {str(val): 0 for val in possible_ratings}
        for r_val in b_ratings:
            key = str(round(r_val, 2))
            if key in hist:
                hist[key] += 1

        n = len(b_ratings)
        avg = round(sum(b_ratings) / n, 2) if n > 0 else 0.0
        
        # Standard deviation (Polarizer metric)
        if n > 1:
            variance = sum((x - avg) ** 2 for x in b_ratings) / n
            std_dev = round(math.sqrt(variance), 2)
        else:
            std_dev = 0.0

        b_notes = [
            {
                "participant_id": r["participant_id"],
                "name": r["participant_name"],
                "avatar": r["participant_avatar"],
                "rating": r["rating"],
                "notes": r["notes"].strip()
            }
            for r in ratings
            if r["beer_id"] == b_id and r.get("notes") and r["notes"].strip()
        ]

        beer_stats[b_id] = {
            "beer_id": b_id,
            "name": b["name"],
            "brewery": b["brewery"],
            "image_url": b["image_url"],
            "order_num": b["order_num"],
            "count": n,
            "average": avg,
            "min": min(b_ratings) if n > 0 else None,
            "max": max(b_ratings) if n > 0 else None,
            "std_dev": std_dev,
            "histogram": hist,
            "ratings_list": b_ratings,
            "notes_list": b_notes
        }

    # Ranked beers by average
    ranked_beers = sorted(
        [s for s in beer_stats.values() if s["count"] > 0],
        key=lambda x: (x["average"], -x["std_dev"]),
        reverse=True
    )
    for idx, r in enumerate(ranked_beers, start=1):
        r["rank"] = idx

    # Participant statistics
    participant_stats: Dict[str, Any] = {}
    for p in participants:
        p_id = p["id"]
        p_ratings = [r for r in ratings if r["participant_id"] == p_id]
        scores = [r["rating"] for r in p_ratings]
        p_avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        participant_stats[p_id] = {
            "id": p_id,
            "name": p["name"],
            "avatar": p["avatar"],
            "ratings_count": len(scores),
            "average_given": p_avg,
            "scores": scores
        }

    # 2. Superlatives calculation
    superlatives: Dict[str, Any] = {}

    if ranked_beers:
        # Champion: Highest average
        superlatives["champion"] = {
            "title": "🏆 Club Champion",
            "subtitle": "Highest average rated beer of the event",
            "name": ranked_beers[0]["name"],
            "brewery": ranked_beers[0]["brewery"],
            "image_url": ranked_beers[0]["image_url"],
            "value": f"{ranked_beers[0]['average']:.2f} / 5.00",
            "beer_id": ranked_beers[0]["beer_id"]
        }

        # Wooden Spoon: Lowest average (if at least 2 beers)
        if len(ranked_beers) >= 2:
            wooden = ranked_beers[-1]
            superlatives["wooden_spoon"] = {
                "title": "🪵 The Wooden Spoon",
                "subtitle": "Lowest rated beer of the night",
                "name": wooden["name"],
                "brewery": wooden["brewery"],
                "image_url": wooden["image_url"],
                "value": f"{wooden['average']:.2f} / 5.00",
                "beer_id": wooden["beer_id"]
            }

        # The Polarizer: Highest standard deviation among beers with >= 2 ratings
        rated_multiple = [b for b in beer_stats.values() if b["count"] >= 2]
        if rated_multiple:
            polarizer = max(rated_multiple, key=lambda x: x["std_dev"])
            if polarizer["std_dev"] > 0:
                superlatives["polarizer"] = {
                    "title": "⚡ The Polarizer",
                    "subtitle": "Most controversial beer with the widest split of opinions",
                    "name": polarizer["name"],
                    "brewery": polarizer["brewery"],
                    "image_url": polarizer["image_url"],
                    "value": f"±{polarizer['std_dev']:.2f} spread",
                    "beer_id": polarizer["beer_id"]
                }

    # Participant Superlatives (if >= 2 participants with ratings)
    active_participants = [p for p in participant_stats.values() if p["ratings_count"] > 0]
    if len(active_participants) >= 2:
        # Toughest Critic: lowest average score given
        toughest = min(active_participants, key=lambda x: x["average_given"])
        superlatives["toughest_critic"] = {
            "title": "🍷 The Toughest Critic",
            "subtitle": "Stingiest with the stars tonight",
            "name": toughest["name"],
            "avatar": toughest["avatar"],
            "value": f"Avg: {toughest['average_given']:.2f}"
        }

        # Generous Soul: highest average score given
        generous = max(active_participants, key=lambda x: x["average_given"])
        superlatives["generous_soul"] = {
            "title": "☀️ The Generous Soul",
            "subtitle": "Showed maximum love with their ratings",
            "name": generous["name"],
            "avatar": generous["avatar"],
            "value": f"Avg: {generous['average_given']:.2f}"
        }

        # Consensus Voice: smallest mean absolute difference from room average
        p_consensus = []
        for p in active_participants:
            p_id = p["id"]
            diffs = []
            for r in ratings:
                if r["participant_id"] == p_id and r["beer_id"] in beer_stats:
                    room_avg = beer_stats[r["beer_id"]]["average"]
                    diffs.append(abs(r["rating"] - room_avg))
            if diffs:
                mean_diff = sum(diffs) / len(diffs)
                p_consensus.append((p, mean_diff))
        
        if p_consensus:
            p_consensus.sort(key=lambda x: x[1])
            voice = p_consensus[0][0]
            superlatives["consensus_voice"] = {
                "title": "🎯 The Room's Pulse",
                "subtitle": "Ratings closest to group consensus",
                "name": voice["name"],
                "avatar": voice["avatar"],
                "value": "Most in-tune"
            }

    return {
        "beer_stats": beer_stats,
        "ranked_beers": ranked_beers,
        "participant_stats": participant_stats,
        "superlatives": superlatives,
        "total_participants": len(participants),
        "total_ratings": len(ratings)
    }
