# 🍻 Beer Club Web Application

A zero-install, real-time web application for hosting blind beer tasting events. Participants join via QR code, taste each pour blindly, and submit scores (`1.00` to `5.00` in `0.25` increments) along with optional tasting notes. The host orchestrates rounds in real time, and at the end of the night, unmasks the beers with full score distributions, club tasting notes, rankings, and fun superlatives!

---

## 🚀 Quick Start (Zero Dependencies)

The app is built entirely with **Python 3 standard library** on the backend and modern vanilla ES6+/CSS on the frontend. No `npm install`, `pip install`, or external database server is required.

To start the server:

```bash
python3 server.py
```

*(Or start with a completely blank slate from the command line using `python3 server.py --fresh`)*

By default, the server listens on port **8080** with clean, simple URLs:
* **Participant Mobile View:** [http://localhost:8080](http://localhost:8080) or [http://localhost:8080/join](http://localhost:8080/join)
* **Host Control Dashboard:** [http://localhost:8080/host](http://localhost:8080/host)

*(To run on a custom port, pass it as an argument: `python3 server.py 3000`)*

---

## 📱 How It Works

### 1. Host Setup, Demo Event & QR Code Display
* Open the **Host Dashboard** at `https://<your-domain>/host` (or `http://<your-ip>:8080/host`).
* **Workflow-Ordered Tabs:** The Host Dashboard tabs are arranged in chronological event order:
  1. **Flight & Event** — Set your Event Title, Theme, Date (via a one-click calendar picker), and Beer Lineup.
  2. **QR & Invites** — Display the scannable QR code, copy the Join URL, or tap **Share** to open your mobile device's native share sheet (SMS, email, AirDrop, etc.).
  3. **Live Pour Control** — Orchestrate active blind rounds and monitor real-time guest ratings.
  4. **Results & Reveal** — Unmask beers, histograms, club tasting notes, and superlatives.
* **Demo Event vs. Custom Event:**
  * By default, the app comes pre-loaded with the **"Fall Brews"** (*Autumnal Themed Beer Flight*) demo event featuring 6 seasonal craft beers.
  * Clicking **"Demo Event"** in the top bar resets the app back to the *Fall Brews* flight at any time so hosts can do a dry run and learn how the app works before hosting.
  * Clicking **"New Blank Event"** wipes all beers, participants, and ratings and opens the **Flight & Event** setup tab so the host can enter their own event title, theme, date, and custom beer lineup.
* **Simple Join URLs & Native Share:**
  * Both `https://<your-domain>` and `https://<your-domain>/join` open the Participant view directly for the active event.
  * On the **QR & Invites** tab, hosts can scan the QR code, click **Copy Link**, or click **Share** to open their phone's native share menu to text or email the invite link.
* Guests scan the code with their phone camera, enter their display name, and pick a tasting badge (`🍺`, `🍻`, `🥨`, `🌾`, `👑`, etc.). Sessions persist in `localStorage` so screen locks or refreshes never lose their place.

### 2. Blind Tasting Rounds (Anti-Spoiler Protected)
* The host pours Beer #1 without revealing the bottle or can.
* While the tasting is active, the server **strictly sanitizes all beer metadata** on `/api/events/<id>/state`:
  * Participants only see `"Beer #1"`, `"Beer #2"`, etc.
  * Real beer names, breweries, ABV, images, and brewer notes are withheld on the server until the final reveal so even tech-savvy guests inspecting network traffic cannot see spoilers.
* Participants rate each pour from **1.00 to 5.00 in 0.25 increments** using a bespoke tactile slider with a live animated SVG pint glass and optional blind tasting notes.
* **Post-Submission Tasting Room Status:** Immediately after submitting a score for the active pour, the participant's screen transitions to a live waiting card showing their locked-in rating, a button to adjust their score if they change their mind, and a real-time room roster showing who has rated and who is still tasting.
* When ready, the host clicks **"Advance to Next Pour"**. All participant phones automatically transition to the next beer via Server-Sent Events (SSE).

### 3. Late Arrivals & Missed Beers (All-Rounds Drawer)
* Late arrivals automatically land on the **active room round** so the group stays in sync.
* During blind tasting, participants can tap the rounds button (`1/6`) in the top header to slide open the **Tasting Flight Rounds** drawer:
  * **Emerald badge:** Rated (`4.25 ★`)
  * **Amber badge:** Unrated
* Tapping any round lets them catch up on a missed pour or update a previous score without disrupting the room.

### 4. The Big Reveal, Tasting Notes & Superlatives
* After the final pour, the host clicks **"Reveal All Beers"**.
* The server unmasks the flight and pushes the reveal screen to every phone in the room.
* **Locked Rounds on Reveal:** Once the beers are revealed, the rounds drawer is hidden and locked so participants can no longer revisit prior rounds to alter their scores after seeing the labels.
* **Participant & Host Reveal Experience:**
  * **Personal Scorecard:** Highlights the participant's personal average, top pour, and lowest-rated pour.
  * **Club Superlatives:**
    * 🏆 **Club Champion:** Highest average rated beer of the night.
    * ⚡ **The Polarizer:** Beer with the widest split of opinions (highest standard deviation).
    * 🪵 **The Wooden Spoon:** Lowest average rated beer.
    * 🍷 **The Toughest Critic:** Participant with the lowest average score.
    * ☀️ **The Generous Soul:** Participant with the highest average score.
    * 🎯 **Consensus Voice:** Participant whose scores aligned closest with the room average.
  * **0.25-Increment Histograms & Tasting Notes:** Every beer card displays an SVG distribution chart across the `1.00`–`5.00` scale alongside the participant's own blind tasting note and all club tasting notes submitted by the room.

---

## 🛠️ Testing

Run the automated unit and integration test suite with:

```bash
python3 test_beerclub.py
```

Tests verify:
* SQLite schema, foreign-key cascades, and lineup re-ordering.
* Strict anti-spoiler masking during active blind tasting vs. full metadata exposure upon reveal.
* `0.25` increment validation and clamping bounds (`1.00` to `5.00`).
* Late arrivals, retroactive rating submissions, and score adjustments.
* Standard deviation, histogram bucketing, and superlative calculations.
* Live HTTP REST endpoints and SVG QR code generation.

---

## 📂 Project Architecture

All files are organized in a flat root directory for effortless single-step uploads to GitHub and cloud hosts (such as Render):

```text
Beer Club/
├── server.py              # Multithreaded HTTP server, SSE real-time broadcaster & REST API
├── db.py                  # SQLite schema, Fall Brews demo seed, anti-spoiler masking & analytics
├── qrcode_gen.py          # Zero-dependency pure Python QR code generator (SVG output)
├── index.html             # Mobile-first participant view (Join, Tasting Slider, Room Status, Reveal)
├── host.html              # Host director dashboard (Live Control, QR Invites, Lineup Setup, Results)
├── style.css              # Modern dark-mode craft taproom design system (responsive mobile & desktop)
├── app.js                 # Participant frontend logic, SSE client, 0.25 slider & rounds drawer
├── host.js                # Host dashboard frontend logic, round stepper, lineup editor & QR sync
├── test_beerclub.py       # Automated unit and integration test suite
├── render.yaml            # Render.com Infrastructure-as-Code blueprint
├── Procfile               # Cloud process launcher definition
├── requirements.txt       # Python dependency manifest (stdlib only)
├── .gitignore             # Excludes local SQLite database files and Python cache from Git
└── README.md              # Project documentation
```
