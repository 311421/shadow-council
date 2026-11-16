# Shadow Council

A playable browser social-deduction MVP.

## Run with Docker

Start Docker Desktop, then run from this folder:

```powershell
docker compose up -d --build --wait
```

Open http://localhost:8000. 

```powershell
docker compose ps                 # status and health
docker compose logs --tail 50 web # recent logs
docker compose stop              # stop, preserving data
docker compose up -d             # start again
docker compose up -d --build     # rebuild after code changes
```
