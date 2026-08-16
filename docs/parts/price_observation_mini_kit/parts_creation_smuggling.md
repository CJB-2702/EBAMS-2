---
okf_version: "0.1"
type: "Explanation"
title: "The Parts-Creation Smuggling System"
description: "How newly created parts reach the pricing screen through a session breadcrumb: the accepted anti-pattern, its containment rules, Django's nested-mutation trap, and why appending is what fixes multi-tab."
tags: [explanation, procurement, parts, session, anti-pattern]
context_tier: 2
personas: [backend, frontend]
---

# The Parts-Creation Smuggling System

**The problem it solves:** users usually know the vendor and the price at the moment they define a
new part. That knowledge is available in `app/parts`, and it needs to end up in a
`PartPriceObservation` row in `app/procurement`. `parts` is not allowed to know procurement exists.

**The solution:** part creation leaves a breadcrumb in the user's session. The pricing screen reads
it and offers to load those parts into a grid. Nothing is passed, nothing is posted, no FK crosses
an app boundary — one module's name is imported in the wrong direction, and that is the whole cost.

This is **D81**, an accepted `# DELIBERATE ANTI-PATTERN`. This document is the containment contract
that makes it acceptable.

---

## Why not the alternatives

| Approach | Why not |
| :--- | :--- |
| Price fields inside the part-create wizard | Entangles the transactions — a bad price row loses twenty parts you just typed. Grows a commercial section on an identity form that most users skip. Twenty rendered form rows beat by one pasted column |
| Move `Vendor` + pricing into `parts` | Moves the ick. `assets` would then depend on `parts` to name a vendor |
| Extract a low `parties/` app | Correct (D79), out of appetite |
| Cross-app HTTP handoff (button POSTs JSON to a procurement seed endpoint) | Genuinely clean — coupling reduces to a URL string in a template. Rejected only because the session path needs no seed endpoint, no CSRF form, no `POST → 303 → GET` dance, and has no querystring ceiling |

---

## Where it lives

```
app/procurement/presentation_layer/tools/recent_part_creations.py
```

Presentation layer, alongside the existing
[`po_wizard_draft.py`](../app/procurement/presentation_layer/tools/po_wizard_draft.py) — this is the
same category of object: a raw session dict, mutated across many requests, never validated, never
written to the database.

The module owns the key. `app/parts` entrypoints import **this module**, which is the inversion.
Marked at the top of the file:

```python
# DELIBERATE ANTI-PATTERN (D81) — app/parts imports this procurement module, inverting
# the project's one-way parts <- procurement dependency. Accepted so that price capture
# stays wholly inside procurement without extracting a parties/ app (D79). Contained to
# the three public functions below; SESSION_KEY is private to this module and nothing
# else in the codebase may read or write it.
```

---

## The payload

```python
SESSION_KEY = "procurement_recent_part_creations"

MAX_PARTS = 100
TTL = timedelta(hours=...)   # value deferred to the app-hardening pass
```

```json
{
  "parts": [
    {"part_id": 41, "created_at": "2026-08-09T14:03:11+00:00", "domain_ids": [3, 7]},
    {"part_id": 42, "created_at": "2026-08-09T14:03:11+00:00", "domain_ids": []}
  ],
  "overflowed": false
}
```

**IDs and timestamps only — no part numbers, no names.** The read path has to re-query anyway (to
re-authorize and to drop soft-deleted parts), so a stored `part_number` buys no queries and adds
staleness risk when a part is renumbered.

**`domain_ids` is the one denormalization worth keeping.** It records which domains the part was
created *for, at creation time* — a fact about the creation event, not about the part. Part-domain
mappings change, so it is not recoverable later, and it is what prefills each observation's domain
in the grid. Store the IDs; re-query the names for display.

At the 100-row cap this is roughly 6 KB of base64 JSON in the `django_session` row. Non-issue.

---

## Session lifetime

Nothing session-related is configured in [`app/config/settings.py`](../app/config/settings.py)
beyond `SESSION_COOKIE_SECURE`, so the project runs on Django defaults:

- **Engine:** database-backed (`django.contrib.sessions` is installed, no `SESSION_ENGINE` override)
- **Age:** `SESSION_COOKIE_AGE` defaults to **1209600 seconds — two weeks**
- **Renewal:** `SESSION_SAVE_EVERY_REQUEST` is unset, so expiry is roughly two weeks from the last
  time the session was *modified*, not from login
- **Browser close:** `SESSION_EXPIRE_AT_BROWSER_CLOSE` unset — the session survives a restart

**Do not shorten `SESSION_COOKIE_AGE` to bound the breadcrumb.** That logs every user out on the
same schedule. The breadcrumb's lifetime is a **per-entry `created_at` filtered on read**, entirely
independent of the cookie. Tightening the cookie age is a separate app-hardening concern and is out
of this kit's scope; `TTL`'s value is left unset for that pass.

---

## The API — three functions, nothing else

```python
def record_created_parts(request, *, part_ids, domain_ids_by_part) -> None:
    """Append. Dedupe by part_id keeping the earliest created_at. Prune expired.
    Fill to MAX_PARTS and set overflowed=True if there is more."""

def read_recent(request, *, actor) -> list[int]:
    """Prune expired, re-authorize against the actor's visible domains, drop
    missing/soft-deleted parts, return what survives."""

def consume(request, *, part_ids) -> None:
    """Remove these part_ids after their observations are committed."""
```

Three functions is not a style preference — it is the containment mechanism. Two of Django's session
hazards below are only survivable because the writeback happens in exactly three places and cannot
be forgotten in a fourth.

---

## Hazard 1: nested mutation does not save

Django's session object tracks a `modified` flag, set by operations **on the session itself** —
`__setitem__`, `__delitem__`, `pop`, `update`, `clear`. `SessionMiddleware` writes to the database at
end-of-response **only if `modified` is True**.

`request.session[SESSION_KEY]` is a `__getitem__`. It hands back the object. Mutating that object
never touches the session:

```python
payload = request.session[SESSION_KEY]   # __getitem__ — modified stays False
payload["parts"].append(row)             # mutates a plain dict in memory
# end of request -> middleware sees modified=False -> nothing is written
```

The failure signature is the reason this deserves its own section. Within that same request it
**looks like it worked** — the in-memory dict is correct, so anything rendered afterwards shows the
new row. The loss appears on the *next* request. And it is intermittent: if anything else in the
same request performs a real session write (a login, a `messages.success()` call, some unrelated
feature setting a key), the whole payload is saved *including* the nested change. It works in some
flows and not others.

**The fix — read, mutate locally, assign the whole key back:**

```python
payload = request.session.get(SESSION_KEY) or {"parts": [], "overflowed": False}
payload["parts"].append(row)
request.session[SESSION_KEY] = payload   # __setitem__ -> modified = True
```

`request.session.modified = True` also works but is a flag every call site must remember.
Reassignment is self-enforcing. `SESSION_SAVE_EVERY_REQUEST = True` would mask the bug globally at
the cost of a database write on every request — do not.

---

## Hazard 2: one session, many tabs

**There is exactly one user session, and every tab shares it.** The session ID lives in the
`sessionid` cookie, which is scoped to browser-profile + domain, not to tabs. Ten tabs send the same
cookie, hit the same `django_session` row, and read and write the same payload.

A *second* session comes from a different browser, an incognito window, or another device — so one
user can hold several concurrent sessions, but never by opening tabs.

This is the whole reason the breadcrumb **appends rather than replaces** (D82). Under replace
semantics, tab A writes `{parts: [41, 42]}`, tab B writes `{parts: [43]}` into the same slot, and
A's batch is gone. Under append, both tabs contribute to one running list, there is no "current
batch" for a second tab to be wrong about, and the union is what the user wanted to see anyway.

---

## Hazard 3: last-write-wins

The payload is serialized and written as **one blob with no locking**. Two overlapping requests can
race:

```
tab A: read {parts:[41]} -> append 42 -> write {parts:[41,42]}
tab B: read {parts:[41]} -> append 43 -> write {parts:[41,43]}   <- A's 42 is gone
```

The race window is **the whole request**, not the few microseconds inside `record_created_parts`.
The session payload is loaded into memory early — `AuthenticationMiddleware` evaluating
`request.user` pulls it at request start — and flushed at end-of-response. A read-mutate-write block
inside the view narrows nothing, because the snapshot was taken before the view ran.

That inverts the obvious intuition: **a long bulk upload is the exposed case, not the safe one.** An
eight-second CSV import holds a request-start snapshot for eight seconds, and its end-of-response
save clobbers anything a quicker tab wrote meanwhile. Interactive wizard submits are effectively
immune — nobody switches tabs and completes a second creation inside the same few hundred
milliseconds.

**Accepted, not mitigated.** The consequence is a part missing from the banner, and:

- the unpriced-parts filter (D86) finds it anyway;
- a bulk upload big enough to be slow is probably overflowing the 100-part cap and routing the user
  to that filter regardless.

The bad case self-selects into the backstop. Locking the session for this would be wildly
disproportionate.

---

## Write only on real success

Session writes are **not** inside the database transaction, and `SessionMiddleware` saves the
session even on a 500 response. So a rollback after the breadcrumb was mutated leaves it pointing at
parts that do not exist.

Use `transaction.on_commit` — the callback only fires if the transaction actually commits:

```python
transaction.on_commit(
    lambda: record_created_parts(
        request, part_ids=ids, domain_ids_by_part=dids
    )
)
```

The read path already drops phantom IDs, so this is belt-and-braces. It is also one line, and it
keeps the session honest rather than making the reader responsible for cleaning up someone else's
rollback.

---

## Re-authorize on every read

Session part IDs are a **convenience, never a capability**. Domain assignments change; a breadcrumb
written Monday must not surface a part the user lost access to on Tuesday.

`read_recent()` filters loaded IDs through the actor's visible-domain set — the same
`_visible_domain_ids(actor)` helper `PartPricePolicy` uses (D84) — and drops what fails **silently,
with no error**. The user simply sees fewer rows. Announcing "3 parts were hidden" leaks the
existence of parts they cannot see.

---

## Call sites

Exactly two, both in `app/parts`, both after commit:

| File | When |
| :--- | :--- |
| [`app/parts/presentation_layer/entrypoints/parts.py`](../app/parts/presentation_layer/entrypoints/parts.py) | After `PartCreationWizardFactory.create()` succeeds |
| [`app/parts/presentation_layer/entrypoints/parts_bulk_upload.py`](../app/parts/presentation_layer/entrypoints/parts_bulk_upload.py) | After the bulk upload transaction commits |

Both carry a one-line `# DELIBERATE ANTI-PATTERN (D81)` comment pointing back at the module, so the
inversion is greppable from either end.

The control layer — `PartCreationWizardFactory`, `PartBulkUploadFactory` — stays completely
ignorant. This is a presentation-layer concern, and keeping it there is what makes the anti-pattern
a wart rather than a wound.
