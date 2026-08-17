---
description: Authenticate against the local Django server using credentials from default_users_passwords.json and save a session cookie for subsequent curl requests.
argument-hint: "[username]  — defaults to the value of default_login in default_users_passwords.json"
---

Credentials are stored in `default_users_passwords.json` at the project root (gitignored).

**Step 0 — read credentials from the JSON file:**

```bash
CREDS_FILE="default_users_passwords.json"

# Use provided argument if given, otherwise fall back to default_login field
TARGET_USER="${1:-$(python3 -c "import json; d=json.load(open('$CREDS_FILE')); print(d['default_login'])")}"

PASSWORD=$(python3 -c "
import json, sys
d = json.load(open('$CREDS_FILE'))
match = next((u for u in d['users'] if u['username'] == '$TARGET_USER'), None)
if not match:
    sys.exit(f'User {repr(\"$TARGET_USER\")} not found in $CREDS_FILE')
print(match['password'])
")

BASE_URL=$(python3 -c "import json; d=json.load(open('$CREDS_FILE')); print(d.get('base_url', 'http://localhost:8000'))")

echo "Logging in as: $TARGET_USER  ($BASE_URL)"
```

**Step 1 — fetch the login page and capture the CSRF cookie:**

```bash
curl -s -c /tmp/dev_cookies.txt "$BASE_URL/" -o /dev/null
```

**Step 2 — extract the CSRF token and POST credentials:**

```bash
CSRF=$(grep csrftoken /tmp/dev_cookies.txt | awk '{print $NF}') && \
curl -s -b /tmp/dev_cookies.txt -c /tmp/dev_cookies.txt \
  -X POST "$BASE_URL/" \
  -d "action=login&username=$TARGET_USER&password=$PASSWORD&csrfmiddlewaretoken=$CSRF" \
  -H "Referer: $BASE_URL/" \
  -o /dev/null -w "Login: %{http_code} -> %{redirect_url}\n"
```

A `302 -> $BASE_URL/` response confirms success.

**Step 3 — verify the session reaches a protected page:**

```bash
curl -s -b /tmp/dev_cookies.txt "$BASE_URL/events/" -o /dev/null -w "%{http_code}\n"
```

Should return `200`. A `302 -> /?next=…` means the session didn't stick.

---

The cookie jar is now at `/tmp/dev_cookies.txt`. Use it for any subsequent curl calls:

```bash
curl -s -b /tmp/dev_cookies.txt "$BASE_URL/<path>/"
```

**Available users** (from `default_users_passwords.json`):

```bash
python3 -c "
import json
d = json.load(open('default_users_passwords.json'))
print(f'default_login: {d[\"default_login\"]}')
for u in d['users']:
    print(f'  {u[\"username\"]:20s} — {u[\"notes\"]}')
"
```
