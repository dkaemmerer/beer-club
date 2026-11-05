# 🍻 Beer Club Web Application

A zero-install, real-time web application for hosting blind beer tasting events. Participants join via QR code, taste each pour blindly, and submit scores (1.00 to 5.00 in 0.25 increments). The host orchestrates rounds in real time, and at the end of the night, unmasks the beers with full score distributions, club rankings, and fun superlatives!

---

## 🚀 Quick Start (Zero Dependencies)

The app is built entirely with **Python 3 standard library** on the backend and modern vanilla ES6+/CSS on the frontend. No `npm install`, `pip install`, or external database is required.

To start the server:

```bash
python3 server.py
```

By default, the server listens on port **8080**:
* **Host Control Dashboard:** [http://localhost:8080/host](http://localhost:8080/host)
* **Participant Mobile View:** [http://localhost:8080/join](http://localhost:8080/join) (or scan the on-screen QR code)

*(To run on a custom port, pass it as an argument: `python3 server.py 3000`)*

---

## 📱 How It Works

### 1. Host Setup & QR Code Display
* Open the **Host Dashboard** at `http://<your-computer-ip>:8080/host`.
* Click the **"📱 QR Code & Invites"** tab.
* Display this QR code on a TV, tablet, or laptop screen.
* Guests scan the code with their mobile cameras and enter their name + choose a fun avatar (🍺, 🍻, 🥨, 🌾, 👑, etc.).
* Their session persists in `localStorage` so screen lock or page refresh never loses their place.

### 2. Blind Tasting Rounds (Anti-Spoiler Protected)
* The host pours Beer #1 without revealing the bottle or can.
* While the tasting is active, the server **strictly sanitizes all beer metadata**:
  * Participants only see `"Round 1: Beer #1 (Blind Tasting)"`.
  * Beer name, brewery, photos, and notes are completely withheld on the server to prevent tech-savvy guests from peeking at browser devtools.
* Participants rate the beer from **1.00 to 5.00 in 0.25 increments** using:
  * Smooth slider or `+0.25` / `−0.25` steppers
  * Quick-select chips (e.g., `3.50`, `3.75`, `4.00`, `4.50`)
  * Optional flavor tags (Citrusy, Piney, Hoppy, Crisp, Malty, etc.) and personal notes.
* The host's screen shows a live submission tracker with real-time green checkmarks as votes arrive.
* When ready, the host clicks **"Advance to Next Beer ➡️"**. All participant screens immediately transition to the next beer via Server-Sent Events (SSE).

### 3. Late Arrivals & Missed Beers (Subtle History Drawer)
* To keep the room synchronized, late arrivals automatically land on the **active room round**.
* If a participant arrived late or stepped away during a round, they can tap the subtle **"📋 Rounds"** button in the top navigation.
* This slides open a discreet drawer showing all beers in the tasting:
  * Green badge = Rated (`⭐ 4.25`)
  * Amber badge = Not rated yet
* Tapping any prior beer allows them to submit or adjust a rating individually without disrupting the rest of the room.

### 4. The Big Reveal & Superlatives
* After the final beer is poured, the host clicks **"🎉 Reveal All Beers!"**.
* The server unmasks the beers and pushes the reveal event to everyone in the room.
* **Participant Reveal Screen:**
  * **Personal Scorecard:** Highlights the participant's personal top pick and lowest-rated beer.
  * **Club Superlatives:**
    * 🏆 **Club Champion:** Highest average rated beer of the event.
    * ⚡ **The Polarizer:** Beer with the highest standard deviation (widest split of opinions).
    * 🪵 **The Wooden Spoon:** Lowest average rated beer.
    * 🍷 **The Toughest Critic:** Participant who gave the lowest average score.
    * ☀️ **The Generous Soul:** Participant who gave the highest average score.
    * 🎯 **The Room's Pulse / Consensus Voice:** Participant whose scores aligned closest with group consensus.
  * **Interactive Histograms:** Every beer displays an interactive SVG bar chart showing the frequency of votes across the entire 1.0 to 5.0 spectrum.

---

## 🛠️ Testing

A comprehensive automated test suite is included:

```bash
python3 test_beerclub.py
```

Tests cover:
* SQLite schema, data integrity, and cascading operations.
* Strict anti-spoiler masking during active blind tasting vs. full exposure upon reveal.
* 0.25 increment validation and rounding bounds.
* Late arrivals, retroactive rating submissions, and score adjustments.
* Standard deviation, room consensus, and superlative mathematics.
* Real-time HTTP REST endpoints and QR code generation.

---

## 📂 Project Architecture

```
Beer Club/
├── server.py              # Multithreaded HTTP server + SSE real-time engine + REST API
├── db.py                  # SQLite schema, queries, anti-spoiler logic, and analytics engine
├── qrcode_gen.py          # Zero-dependency pure Python QR code generator (SVG output)
├── test_beerclub.py       # Comprehensive unit and integration test suite
├── static/
│   ├── index.html         # Mobile-first participant view & reveal experience
│   ├── host.html          # Host orchestration dashboard, QR display & lineup manager
│   ├── css/
│   │   └── style.css      # Dark-mode pub aesthetic design system (responsive, high-contrast)
│   └── js/
│       ├── app.js         # Participant state manager, SSE client, 0.25 slider & drawer
│       └── host.js        # Host dashboard manager, live submission ticker & controls
└── README.md              # Project documentation
```
