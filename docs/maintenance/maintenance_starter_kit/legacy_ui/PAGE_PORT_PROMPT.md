# Page port prompt template

Copy-paste template for starting a **fresh conversation** to port or fix one
page against its legacy original. One page per conversation — the context stays
small and the review stays honest.

Fill the four bracketed slots. Everything else is boilerplate.

---

## The template

```
Port one page faithfully from the legacy app.

  NEW (EBAMS-2):  [NEW_URL]
  OLD (legacy):   [OLD_URL]

## Reference material — read these first, in this order

1. `maintenance_starter_kit/legacy_ui/page_catalog.md` — find the entry whose
   legacy URL matches OLD above. It gives the page's card-by-card anatomy and
   names its screenshot file.
2. `maintenance_starter_kit/legacy_ui/screenshots/<file>.png` — READ THE IMAGE.
   The catalog prose is a summary; the screenshot is the source of truth for
   layout, ordering, density, and anything the prose missed.
3. `maintenance_starter_kit/legacy_ui/gap_analysis.md` — search for this page.
   If it has an entry, that entry lists what is already known to be missing.
4. `maintenance_starter_kit/legacy_ui/route_inventory.md` — every legacy route
   this page fires (its POST verbs, its HTMX fragments).

Then read the legacy source it names under `/home/cb/REPOS/asset_management/`
(routes + templates) and the current EBAMS-2 view/template pair.

## Seeing both pages live

Legacy (Flask, port 5000) — back up the DB first, and do NOT use `./run`,
which calls `z_clear_data.py`:

    cp ~/REPOS/asset_management/instance/asset_management.db /tmp/old_db_backup.db
    cd ~/REPOS/asset_management && nohup ./venv/bin/python3 app.py > /tmp/oldapp.log 2>&1 &

Log in as `admin` / `admin987654321!`.

EBAMS-2 (Django, port 8000):

    ./run.sh          # ./stop.sh to stop

Log in as `generic_admin` / `changeme` (see `default_users_passwords.json`).

Screenshot either side with playwright from the ebams2 venv — see
`maintenance_starter_kit/legacy_ui/capture_screenshots.py` for a working
login-then-shoot script to crib from.

## What "faithful" means here

Reproduce the legacy page's **information architecture and capabilities**:
every card, every field, every action, every empty state, in the same order and
grouping. Do NOT reproduce its visual style — this is Bulma + HTMX with sharp
corners, not Bootstrap.

Where the legacy page is wrong or vestigial, say so and skip it rather than
porting the mistake. Flag anything you skip.

## Constraints

- `.claude/CLAUDE.md` always-apply rules, especially #5: a card renders even
  when empty, with an explicit empty state.
- `harness/Architecture/` layer rules — writes go through the control layer,
  never from the entrypoint. If a needed verb doesn't exist, add it to the
  owning app's control layer, not inline.
- `harness/UX_UI/` — `format=` for density and HTMX fragments, one canonical URL
  per resource, no parallel fragment-only routes, assignment never in a modal.
- The F5 rule: every state must survive a plain full-page reload.
- Schema changes mean a full `python refresh_project.py`, not an incremental
  migration. Say so before you make one.

## Definition of done

- [ ] The page renders at NEW_URL with real seeded data
- [ ] Every action on the legacy page either works or is explicitly listed as
      deferred, with a reason
- [ ] Reachable from the sidebar (`maintenance/base.html`) and/or the topnav
      popover (`app/public_app/templates/shared/topnav.html`)
- [ ] Cross-linked from wherever the legacy page was reached
- [ ] `./venv/bin/python manage.py check` passes
- [ ] A side-by-side screenshot pair, old vs new, so I can eyeball the diff
- [ ] Tests for any new control-layer verb or guard you added

## Report back

A short list of: what matched, what you changed on purpose and why, what you
skipped, and what you're unsure about. Don't bury a judgement call in a diff.
```

---

## Filled example

For the page in the original request:

```
Port one page faithfully from the legacy app.

  NEW (EBAMS-2):  http://localhost:8000/maintenance/template/2
  OLD (legacy):   https://ebamscore.com/maintenance/maintenance-template/2/view
                  (local: http://127.0.0.1:5000/maintenance/maintenance-template/2/view)

[…rest of the template verbatim…]
```

That one resolves to **page_catalog.md §8**, screenshots
`09_maintenance_template_2_view.png` and `10_maintenance_template_1_view.png`,
and **gap_analysis.md §3**, which already lists what `template_detail.html` is
missing: the four stat tiles, the per-step tools sub-panel and safety callout,
the three roll-up cards, the Deactivate action, and the proto-action advisory.

---

## Notes on using this

- **One page per conversation.** Two pages in one session means the second gets
  the leftovers of the first's context budget.
- **Give both URLs even when the new page doesn't exist yet** — a 404 at NEW_URL
  is a useful, unambiguous starting state.
- **The screenshot is the spec.** If the prose in `page_catalog.md` and the PNG
  disagree, the PNG wins; fix the prose while you're there.
- **For pages with no legacy original** (anything invented for EBAMS-2), drop
  the OLD line and the reference-material section, and describe the page in
  prose instead.
