# Shadow Council

A playable browser social-deduction MVP.

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
