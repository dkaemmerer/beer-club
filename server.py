"""
Beer Club - Real-Time Server
Handles HTTP REST APIs, Server-Sent Events (SSE) broadcasting, and static file serving.
Zero external dependencies (pure Python standard library).
"""

import sys
import os
import json
import socket
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import threading
import queue
import time
import mimetypes

import db
import qrcode_gen

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static") if os.path.isdir(os.path.join(BASE_DIR, "static")) else BASE_DIR

# Pub/Sub manager for SSE
class SSEManager:
    def __init__(self):
        self.lock = threading.Lock()
        # event_id -> list of Queue objects
        self.listeners = {}

    def subscribe(self, event_id: str) -> queue.Queue:
        q = queue.Queue(maxsize=100)
        with self.lock:
            if event_id not in self.listeners:
                self.listeners[event_id] = []
            self.listeners[event_id].append(q)
        return q

    def unsubscribe(self, event_id: str, q: queue.Queue):
        with self.lock:
            if event_id in self.listeners and q in self.listeners[event_id]:
                self.listeners[event_id].remove(q)
                if not self.listeners[event_id]:
                    del self.listeners[event_id]

    def broadcast(self, event_id: str, event_type: str, data: dict):
        payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        with self.lock:
            if event_id in self.listeners:
                for q in list(self.listeners[event_id]):
                    try:
                        q.put_nowait(payload)
                    except queue.Full:
                        pass

sse_manager = SSEManager()

def get_lan_ip():
    """Detects primary local network IP to make QR scanning effortless."""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        return ip
    except Exception:
        return '127.0.0.1'
    finally:
        if s:
            s.close()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class BeerClubHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, format, *args):
        # Concise logging
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {args[0]} {args[1]} {args[2]}\n")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=400):
        self.send_json({"error": message}, status=status)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Route aliases for clean URLs & flat-file upload fallback
        if path == "/" or path == "/join":
            self.path = "/index.html"
            return super().do_GET()
        if path == "/host":
            self.path = "/host.html"
            return super().do_GET()
        if path in ("/css/style.css", "/js/app.js", "/js/host.js"):
            sub_candidate = os.path.join(STATIC_DIR, path.lstrip("/"))
            if not os.path.isfile(sub_candidate):
                self.path = "/" + os.path.basename(path)
            return super().do_GET()

        # SSE Stream
        if path.startswith("/api/events/") and path.endswith("/stream"):
            parts = path.strip("/").split("/")
            event_id = parts[2]
            self.handle_sse_stream(event_id)
            return

        # QR Code generator endpoint
        if path == "/api/qrcode":
            text = query.get("text", [""])[0]
            if not text:
                self.send_error_json("Missing 'text' query parameter")
                return
            svg = qrcode_gen.generate_svg(text)
            svg_bytes = svg.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(svg_bytes)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(svg_bytes)
            return

        # Server info & LAN IP
        if path == "/api/info":
            self.send_json({
                "lan_ip": get_lan_ip(),
                "port": PORT
            })
            return

        # List events
        if path == "/api/events":
            events = db.list_events()
            self.send_json({"events": events})
            return

        # Participant state (Anti-spoiler compliant)
        if path.startswith("/api/events/") and path.endswith("/state"):
            parts = path.strip("/").split("/")
            event_id = parts[2]
            participant_id = query.get("participant_id", [None])[0]
            state = db.get_participant_state(event_id, participant_id)
            if not state:
                self.send_error_json("Event not found", 404)
                return
            self.send_json(state)
            return

        # Host state (Full access)
        if path.startswith("/api/events/") and path.endswith("/host_state"):
            parts = path.strip("/").split("/")
            event_id = parts[2]
            state = db.get_host_state(event_id)
            if not state:
                self.send_error_json("Event not found", 404)
                return
            self.send_json(state)
            return

        # Fallback to static web assets only (never expose .db or .py files)
        allowed_exts = (".html", ".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".ico")
        if not path.endswith(allowed_exts):
            self.send_error_json("Not found", 404)
            return
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
            data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception as e:
            self.send_error_json(f"Invalid JSON: {str(e)}")
            return

        # Create event
        if path == "/api/events":
            title = data.get("title", "Beer Tasting Night")
            theme = data.get("theme", "")
            date = data.get("date", time.strftime("%Y-%m-%d"))
            beers = data.get("beers", [])
            event_id = db.create_event(title, theme, date, beers)
            self.send_json({"event_id": event_id})
            return

        # Participant join
        if path.startswith("/api/events/") and path.endswith("/join"):
            event_id = path.strip("/").split("/")[2]
            name = data.get("name", "").strip()
            avatar = data.get("avatar", "🍺")
            p_id = data.get("participant_id")
            if not name:
                self.send_error_json("Name is required")
                return
            participant = db.join_or_get_participant(event_id, name, avatar, p_id)
            # Broadcast participant join
            sse_manager.broadcast(event_id, "participant_joined", {
                "id": participant["id"],
                "name": participant["name"],
                "avatar": participant["avatar"]
            })
            self.send_json({"participant": participant})
            return

        # Submit / edit rating
        if path.startswith("/api/events/") and path.endswith("/rate"):
            event_id = path.strip("/").split("/")[2]
            p_id = data.get("participant_id")
            beer_id = data.get("beer_id")
            rating = data.get("rating")
            tags = data.get("tags", [])
            notes = data.get("notes", "")

            if not p_id or not beer_id or rating is None:
                self.send_error_json("Missing required fields")
                return

            saved_rating = db.submit_rating(event_id, beer_id, p_id, rating, tags, notes)
            # Broadcast rating update to host & participants (do not leak score to participants)
            sse_manager.broadcast(event_id, "rating_update", {
                "participant_id": p_id,
                "beer_id": beer_id
            })
            self.send_json({"rating": saved_rating})
            return

        # Host change active round
        if path.startswith("/api/events/") and path.endswith("/round"):
            event_id = path.strip("/").split("/")[2]
            current_beer_index = int(data.get("current_beer_index", 1))
            db.update_event_round(event_id, current_beer_index)
            sse_manager.broadcast(event_id, "round_change", {
                "current_round": current_beer_index
            })
            self.send_json({"current_beer_index": current_beer_index})
            return

        # Host reveal
        if path.startswith("/api/events/") and path.endswith("/reveal"):
            event_id = path.strip("/").split("/")[2]
            db.set_event_status(event_id, "revealed")
            sse_manager.broadcast(event_id, "reveal", {
                "status": "revealed"
            })
            self.send_json({"status": "revealed"})
            return

        # Host reset / change status
        if path.startswith("/api/events/") and path.endswith("/status"):
            event_id = path.strip("/").split("/")[2]
            status = data.get("status", "active")
            db.set_event_status(event_id, status)
            sse_manager.broadcast(event_id, "status_change", {
                "status": status
            })
            self.send_json({"status": status})
            return

        # Host add beer
        if path.startswith("/api/events/") and path.endswith("/beers"):
            event_id = path.strip("/").split("/")[2]
            name = data.get("name", "New Beer")
            brewery = data.get("brewery", "")
            style = data.get("style", "")
            abv = float(data.get("abv", 0.0) or 0.0)
            image_url = data.get("image_url", "")
            notes = data.get("notes", "")
            beer_id = db.add_beer(event_id, name, brewery, style, abv, image_url, notes)
            sse_manager.broadcast(event_id, "lineup_change", {"added_beer_id": beer_id})
            self.send_json({"beer_id": beer_id})
            return

        # Host update event details
        if path.startswith("/api/events/") and path.endswith("/details"):
            event_id = path.strip("/").split("/")[2]
            title = data.get("title", "Beer Tasting Night")
            theme = data.get("theme", "")
            date = data.get("date", "")
            db.update_event_details(event_id, title, theme, date)
            sse_manager.broadcast(event_id, "status_change", {"updated": True})
            self.send_json({"updated": True})
            return

        # Host reorder beer
        if path.startswith("/api/beers/") and path.endswith("/move"):
            beer_id = path.strip("/").split("/")[2]
            direction = data.get("direction", "up")
            db.move_beer(beer_id, direction)
            self.send_json({"moved": True})
            return

        # Host reset event to blank slate
        if path.startswith("/api/events/") and path.endswith("/reset"):
            event_id = path.strip("/").split("/")[2]
            db.reset_event_blank(event_id)
            sse_manager.broadcast(event_id, "event_reset", {"reset": True})
            self.send_json({"reset": True, "event_id": event_id})
            return

        self.send_error_json("Unknown endpoint", 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/beers/"):
            beer_id = path.strip("/").split("/")[2]
            db.delete_beer(beer_id)
            self.send_json({"deleted": True})
            return
        self.send_error_json("Unknown endpoint", 404)

    def handle_sse_stream(self, event_id: str):
        """Long-lived Server-Sent Events stream for real-time sync."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Send initial connected ping
        self.wfile.write(b": connected\n\n")
        self.wfile.flush()

        q = sse_manager.subscribe(event_id)
        try:
            while True:
                try:
                    # Timeout after 15s to send keepalive comment
                    msg = q.get(timeout=15.0)
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # Keepalive comment
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            sse_manager.unsubscribe(event_id, q)

def run_server(port=PORT, fresh=False):
    db.init_db()
    if fresh:
        db.reset_event_blank("craft-showdown")
        print(" [!] Started with a fresh, empty event (0 beers, 0 participants).")
    else:
        db.seed_sample_event()
    lan_ip = get_lan_ip()
    server_address = ('0.0.0.0', port)
    httpd = ThreadingHTTPServer(server_address, BeerClubHandler)
    print("=" * 60)
    print(" 🍻 BEER CLUB SERVER STARTED")
    print("=" * 60)
    print(f" Local URL:        http://localhost:{port}")
    print(f" Participant URL:  http://{lan_ip}:{port}/join?event=craft-showdown")
    print(f" Host Dashboard:   http://{lan_ip}:{port}/host?event=craft-showdown")
    print("=" * 60)
    httpd.serve_forever()

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    port = int(args[0]) if args else PORT
    fresh = ("--fresh" in flags or "--empty" in flags or "--clean" in flags)
    run_server(port, fresh=fresh)
