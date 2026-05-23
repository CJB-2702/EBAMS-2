# Testing conventions

Testing conventions for the project. This document is the source of truth for *how* tests are written; CI configuration lives in the repo root.

## Test runners

- **Default:** `pytest` with `pytest-django`. Database access is opt-in via the `django_db` fixture; tests that need DB but forget the marker must fail loudly rather than silently bypass.
- **Factory data:** prefer `factory_boy` factories over fixtures for per-test data. Fixtures are reserved for static reference data and seeded demo state (see [seeding.md](seeding.md)).

## What to test, and where

| Layer | Test target | Notes |
| :--- | :--- | :--- |
| Models | DB-level constraints, choices, custom managers | Don't write tests for `__str__` unless the format matters to a feature. |
| Control layer | Domain verbs, transaction boundaries, guard failure modes | This is the most valuable test surface — every Context and Handler gets a focused test. |
| Search | Complex queryset shape, prefetch hops, `to_dict()` output | Snapshot the struct's dict to catch regressions in shape. |
| Entrypoints | HTTP wiring, status codes, permission gates | One happy-path test per route; cover one failure path per status code. |
| Templates | Rendering smoke tests on key partials | Use `Client.get(...)` + `assertContains` for critical surfaces; do not unit-test every fragment. |

## Test conventions

- **Test files mirror source files** — `test_<module>.py` next to the source under `tests/`, or co-located in a `tests/` package per layer.
- **One concept per test.** Long combinatorial tests obscure failures; split.
- **Name tests as English sentences.** `test_cancel_event_rejects_non_owner` is better than `test_cancel_event_403`.
- **Use the `django_db` marker explicitly.** Tests that need the database declare it; tests that do not must not silently get one.
- **No mocks for the database.** Integration tests hit a real test DB. Mocking the ORM hides migration bugs (this rule was set after a prior incident).

## Fixtures vs factories

- **Factory-by-default** for unit tests.
- **Fixtures** for seeded demo data and for tests that explicitly assert against a stable snapshot.
- **Never load `seed_dev` data into the test DB** — `seed_dev` is for the developer's local environment, not for assertions.

## Speed budget

- A focused unit test should run in < 50 ms.
- A view-level integration test should run in < 200 ms.
- The full suite should finish in under five minutes on a developer laptop. Tests slower than this are quarantined and either rewritten or moved into a nightly job.
