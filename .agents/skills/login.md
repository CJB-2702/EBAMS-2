---
description: Perform authentication against local Django server for generic_admin (or specified user) using credentials from default_users_passwords.json.
argument-hint: "[username] — defaults to generic_admin (password: changeme)"
---

# Dev Login Skill

Default credentials are stored in `default_users_passwords.json`:
- **Default Admin**: `generic_admin` / `changeme`
- **Default Manager**: `generic_manager` / `changeme`
- **Default User**: `generic_user` / `changeme`

## 1. Browser Subagent Login Procedure
When using `browser_subagent` to test authenticated pages:
1. Navigate to `http://127.0.0.1:8000/` (public login page).
2. Fill input `#id_username` (or `input[name="username"]`) with `generic_admin` (or specified user).
3. Fill input `#id_password` (or `input[name="password"]`) with `changeme`.
4. Click the `Sign in` button or submit the form.
5. Verify login redirect (redirects to `/` or protected target).

## 2. Curl / CLI Session Login Procedure
To perform HTTP requests via `curl` with a saved cookie jar (`/tmp/dev_cookies.txt`):

```bash
CREDS_FILE="default_users_passwords.json"
TARGET_USER="${1:-generic_admin}"
PASSWORD=$(python3 -c "import json; d=json.load(open('$CREDS_FILE')); print(next(u['password'] for u in d['users'] if u['username']=='$TARGET_USER'))")
BASE_URL="http://127.0.0.1:8000"

# Fetch login page and CSRF cookie
curl -s -c /tmp/dev_cookies.txt "$BASE_URL/" -o /dev/null
CSRF=$(grep csrftoken /tmp/dev_cookies.txt | awk '{print $NF}')

# POST login form
curl -s -b /tmp/dev_cookies.txt -c /tmp/dev_cookies.txt \
  -X POST "$BASE_URL/" \
  -d "action=login&username=$TARGET_USER&password=$PASSWORD&csrfmiddlewaretoken=$CSRF" \
  -H "Referer: $BASE_URL/" \
  -o /dev/null -w "Login HTTP %{http_code}\n"
```
