# Shadow Council

A playable browser social-deduction MVP built with Django, SQLite, and guest sessions. No Node build, Redis, accounts, or WebSocket service required.

## Run with Docker

Start Docker Desktop, then run from this folder:

```powershell
docker compose up -d --build --wait
```

Open http://localhost:8000. The container runs Gunicorn as a non-root user, serves static assets with WhiteNoise, applies migrations on startup, and stores SQLite plus its session-signing key in the named volume `shadow-council_council-data`. The first container launch in this workspace was seeded with the existing database and signing key, so saved rooms and guest cookies are retained. Subsequent launches preserve the volume automatically; the host `db.sqlite3` is a separate snapshot and is no longer the running container's database.

```powershell
docker compose ps                 # status and health
docker compose logs --tail 50 web # recent logs
docker compose stop              # stop, preserving data
docker compose up -d             # start again
docker compose up -d --build     # rebuild after code changes
```

The published port binds to this PC's loopback interface. Local HTTP cookies are enabled explicitly while Django debug pages remain disabled. For an HTTPS deployment, enable `DJANGO_COOKIE_SECURE=1` and configure the hostname/proxy for that deployment. To use another local port, set `$env:APP_PORT = '8001'` before starting Compose. Avoid `docker compose down -v` unless you intend to delete the saved rooms and sessions.

## Run on Windows

Use Python 3.10–3.14 (Django 5.2's officially supported versions).
This checkout also passed its checks on the installed Python 3.15.2; use a supported Python version for deployment.

```powershell
cd C:\Users\Xozain\shadow-council
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open http://localhost:8000. Create a room and send the invite to 3–9 friends. Each player needs a separate browser profile/device. Multiple tabs in the same profile share one guest identity; one incognito profile also shares cookies between its tabs.

The included `start.ps1` runs migrations and starts the server after dependencies are installed.

## Play over your local network

```powershell
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,192.168.1.42'
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

Replace the example IP with your PC's local IPv4 address. Friends on the same network visit `http://YOUR-IP:8000`; allow the port through your private-network firewall if necessary. A localhost invite only works on your own computer. Internet play needs a deployed Python server and HTTPS.

## Quest Director's Cut

New rooms use the supplied Quest Director's Cut Unofficial Rulebook v2. Existing Resistance games retain their rules until a rematch; the host may open a Quest rematch when finished.

- 4–10 players. Characters and faction counts follow the rulebook. A random Good card remains undealt in 4–5-player games. The host chooses Youth or Troublemaker for 6+ players, and either four-player board.
- Leaders choose a party and assign Magic, with no party vote. Magic forces Success, except Youth must play Failure and Morgan may choose either card. Other Good characters must play Success; other Evil may choose either unless Magic forces Success.
- Party sizes: four-player board A 3/2/3/2 or B 3/2/2/3; 5–7 players 3/2/3/4/3; 8–10 players 4/3/4/5/4. Expedition 4 needs two Failures with 7+ players, and expedition 3 also needs two with 8+.
- The outgoing leader chooses an unused leader. Veterans and amulet holders cannot become leaders. Each person leads once.
- Amulets occur after expedition 4 (6 players), after 3 and 4 (7 players), or after 2, 3, and 4 (8+). The outgoing leader chooses a different eligible holder alongside the next leader. The holder privately checks a player who has never held an amulet or previously been checked. Troublemaker appears Evil to every allegiance check.
- Cleric privately knows the first leader's apparent allegiance. Morgan and Minions know one another; they also know the Hunter with 4–5 players. Blind Hunter never knows teammates.
- Three successes immediately win for Good. Three failures (two with four players) begin an enforced five-minute discussion, followed by the Hunter's decision. There is no timer bypass in the public API.
- Hunt: the Hunter reveals, then guesses two distinct Good targets and their roles, including Cleric. The undealt Good card can be targeted in 4–5-player games. Duke and Archduke can be named as Loyal Servant. Both correct wins for Evil, otherwise Good wins. No Last Chance follows a Hunt.
- Last Chance: all players secretly accuse two distinct players. After all lock in, Evil's hands are discarded and roles reveal. Duke may remove one remaining accusation; Archduke may redirect one; either may pass. The union of Good's remaining targets must equal exactly the Evil players.
- If every expedition leader was Evil, Good wins even when the Hunt or Last Chance would otherwise award Evil victory.
- All player choices use the portraits on the board. Each action has a separate selection and Accept button: choose the entire party, accept it, then choose Magic and accept it. Successor, amulet holder, and each Hunt target/role are also accepted separately. Click a selected portrait or card again to deselect it in place. Back restores the previous accepted action for editing. Character guesses and lobby settings use cards; live updates preserve valid selections.
- Duke then Archduke is the fixed adjustment order when both are present (10 players); the rulebook does not explicitly specify their relative order. Physical silence and role-discussion etiquette rely on players honoring the prompts; the game has no integrated voice/chat.

Use a voice call or play in the same room. Cookies preserve guest seats; losing cookies or abandoning a seat may stall a game. No matchmaking, bots, or spectators are included.

## Saved Resistance template

The pre-Quest implementation, including its party voting table and five attempt squares per expedition, is saved as the personal skill `artifact-template-shadow-council-resistance` and a source ZIP under `C:/Users/Xozain/shadow-council-backups`. Its database and development signing key are backed up separately there; neither is included in the reusable template. `LATEST.txt` identifies that backup.

## Implementation

- `game/engine.py`: ruleset router; `game/quest.py`: Quest engine and private views; `game/resistance.py`: preserved Resistance rules.
- `game/views.py`: guest authentication, room endpoints, and short atomic writes.
- `game/models.py`: room JSON snapshots/version and private guest-to-seat mapping.
- `static/game.js`: browser UI and one-second polling (paused while the tab is hidden).
- SQLite `IMMEDIATE` transactions serialize writes before state reads. Every action includes a version, so stale/duplicate actions cannot apply twice. On a conflict, review the updated room and submit again.
- Private state endpoints send `Cache-Control: no-store`. Normal Django CSRF protection applies to all mutations. Hidden roles, pending vote values, and mission cards are filtered on the server.
- Guest credentials stay in server-side Django sessions; public seat IDs are not login credentials. Sessions expire after 30 days.
- The role hide/reveal button provides screen privacy only; your own role is necessarily available in your browser's network tools.
- System fonts work offline; Google Fonts are an optional visual enhancement.

### What are WebSockets?

With ordinary HTTP, the browser asks and the server answers. Polling repeats that request every second to discover changes. A WebSocket keeps a two-way connection open: the server can immediately notify every player when something happens. Polling is sufficient for this small turn-based game. A later Django Channels + Redis integration can replace polling without rewriting the rules engine.

## Verify

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
node --check static/game.js
node --test tests/vote-history.test.cjs
node --test tests/quest-choices.test.cjs
```

Tests use a separate file-backed SQLite database to exercise concurrent writes. Django creates and removes it during tests. Tests cover complete HTTP games, role privacy, session identity, CSRF, stale actions, Magic restrictions, amulets, character knowledge, Hunt and Last Chance outcomes, legacy voting, and SQLite concurrency.

## Deployment boundary

This is a local development MVP. For a public deployment, set `DJANGO_DEBUG=0`, a strong `DJANGO_SECRET_KEY`, and `DJANGO_ALLOWED_HOSTS`; use an HTTPS Python host, a production WSGI/ASGI server, persistent storage for SQLite, and a static-file service after `collectstatic`. Add request throttling and room cleanup before opening anonymous room creation to the public. Do not expose Django's development server directly to the internet. SQLite suits small games on one host; multiple replicas require a shared database.
