---
description: Authenticate as the dev admin against the local Django server and save a session cookie for subsequent curl requests.
---

Run the following bash commands in sequence to log in as `generic_admin` and verify the session works.

**Dev credentials** (set by `manage.py seed_dev`):

| Username | Password | Notes |
|---|---|---|
| `generic_admin` | `changeme` (or `$SEED_USER_PASSWORD`) | Staff; full portal access |
| `generic_manager` | same | Staff; scoped org access |
| `generic_user` | same | Basic portal access |
| `super_admin` | `$DJANGO_SUPERUSER_PASSWORD` | Django `/admin/` only |

**Step 1 — fetch the login page and capture the CSRF cookie:**

```bash
curl -s -c /tmp/dev_cookies.txt http://localhost:8000/ -o /dev/null
```

**Step 2 — extract the CSRF token and POST credentials:**

```bash
CSRF=$(grep csrftoken /tmp/dev_cookies.txt | awk '{print $NF}') && \
curl -s -b /tmp/dev_cookies.txt -c /tmp/dev_cookies.txt \
  -X POST http://localhost:8000/ \
  -d "action=login&username=generic_admin&password=changeme&csrfmiddlewaretoken=$CSRF" \
  -H "Referer: http://localhost:8000/" \
  -o /dev/null -w "Login: %{http_code} -> %{redirect_url}\n"
```

A `302 -> http://localhost:8000/` response confirms success.

**Step 3 — verify the session reaches a protected page:**

```bash
curl -s -b /tmp/dev_cookies.txt http://localhost:8000/events/ -o /dev/null -w "%{http_code}\n"
```

Should return `200`. A `302 -> /?next=…` means the session didn't stick.

---

The cookie jar is now at `/tmp/dev_cookies.txt`. Use it for any subsequent curl calls:

```bash
curl -s -b /tmp/dev_cookies.txt http://localhost:8000/<path>/
```

To check rendered HTML of a specific page:

```bash
curl -s -b /tmp/dev_cookies.txt http://localhost:8000/<path>/ | grep -i "card-footer\|overflow"
```
