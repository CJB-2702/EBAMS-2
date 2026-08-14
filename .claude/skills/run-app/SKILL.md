---
name: run-app
description: Launch and stop the Django dev server for this project using the repo's own run.sh/stop.sh scripts, instead of invoking `python manage.py runserver` directly.
---

# Running this app

This project has its own launch/stop scripts at the repo root. Use them
instead of hand-rolling a `runserver` invocation.

## Start

```bash
./run.sh
```

This activates `venv/bin/activate`, starts `python manage.py runserver` in
its own session via `setsid` (so its autoreload child shares one process
group), backgrounds it, and writes the leader PID to `.server.pid`.

The server listens on `http://localhost:8000` by default.

## Stop

```bash
./stop.sh
```

Reads `.server.pid`, confirms the process is alive, and sends `SIGTERM` to
the whole process group (`-$PID`) so the autoreload child dies too, then
removes the PID file.

## Notes

- If `./run.sh` reports the server already started but a `curl` smoke test
  fails, check `.server.pid` for a stale/dead PID and rerun `./stop.sh`
  first — it handles the stale-PID case (removes the file and exits
  non-zero) so a retry of `./run.sh` starts clean.
- After starting, verify with a smoke request, e.g.
  `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/`.
- `refresh_project.py` already stops the server (if running via `./run.sh`)
  before wiping the database — no need to `./stop.sh` first when using that
  script.

## Logging in to test a page

Nearly every route requires an authenticated session (see
`LoginRequiredMiddleware` in CLAUDE.md). After `./run.sh`, use the
`dev-login` skill to authenticate via curl and get a reusable session
cookie jar — do not hand-roll this, it already handles the CSRF
round-trip. In short:

```bash
CREDS_FILE="default_users_passwords.json"   # gitignored; project root
TARGET_USER="generic_admin"                 # or any username in the file
BASE_URL="http://localhost:8000"

curl -s -c /tmp/dev_cookies.txt "$BASE_URL/" -o /dev/null
CSRF=$(grep csrftoken /tmp/dev_cookies.txt | awk '{print $NF}')
PASSWORD=$(python3 -c "import json; d=json.load(open('$CREDS_FILE')); print(next(u['password'] for u in d['users'] if u['username']=='$TARGET_USER'))")
curl -s -b /tmp/dev_cookies.txt -c /tmp/dev_cookies.txt \
  -X POST "$BASE_URL/" \
  -d "action=login&username=$TARGET_USER&password=$PASSWORD&csrfmiddlewaretoken=$CSRF" \
  -H "Referer: $BASE_URL/" \
  -o /dev/null -w "Login: %{http_code} -> %{redirect_url}\n"
```

A `302 -> $BASE_URL/` confirms login. Reuse `/tmp/dev_cookies.txt` as the
`-b` cookie jar for any subsequent `curl` calls against protected routes,
e.g.:

```bash
curl -s -b /tmp/dev_cookies.txt -o /dev/null -w '%{http_code}\n' \
  "$BASE_URL/procurement/purchase-orders/create/"
```

If `default_users_passwords.json` doesn't exist yet (it's gitignored),
create it with the dev fixture users — all dev-seeded users get the
password set in `dev_users.json`'s fixture (`changeme` as of the last
`refresh_project.py` run). Format:

```json
{
  "default_login": "generic_admin",
  "base_url": "http://localhost:8000",
  "users": [
    {"username": "generic_admin", "password": "changeme", "notes": "..."}
  ]
}
```
