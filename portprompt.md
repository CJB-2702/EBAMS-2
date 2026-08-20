# Port prompt template

**For dispatching pages:** Use [DISPATCHING_PORT_PROMPT.md](maintenance_starter_kit/legacy_ui/DISPATCHING_PORT_PROMPT.md) instead — it includes dispatching-specific constraints and workflow details.

**For maintenance pages:** Use this template.

---

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


here is a collection of stored images to refrence 
/home/cb/REPOS/ebams2/maintenance_starter_kit/legacy_ui/screenshots
44
6.7M	.
00_maintenance_index.png
01_manager_dashboard.png
02_manager_part_demands.png
03_part_demand_1_view.png
04_part_demand_3_view.png
05_manager_create_assign.png
06_manager_create_assign_create.png
07_manager_create_assign_unassigned.png
08_manager_build_maintenance_templates.png
09_maintenance_template_2_view.png
10_maintenance_template_1_view.png
11_view_templates.png
12_proto_actions_list.png
13_proto_action_1_view.png
14_proto_action_create.png
15_manager_maintenance_plans.png
16_maintenance_plan_3_view.png
17_maintenance_plan_create.png
18_maintenance_plan_3_edit.png
19_maintenance_plan_3_plan.png
20_technician_dashboard.png
21_fleet_dashboard.png
22_manager_view_maintenance.png
23_manager_plan_maintenance.png
24_manager_assign_monitor.png
25_view_events.png
26_event_21_view.png
27_event_21_edit.png
28_event_21_work.png
29_event_21_assign.png
30_event_22_view.png
31_template_builder_drafts.png
32_template_builder_new.png
33_action_creator_portal_set1.png
34_template_builder_1_edit.png
35_template_builder_1_action_creator.png
36_event_22_edit.png
37_event_22_work.png
38_event_22_assign.png
39_technician_most_recent_event.png
40_maintenance_plan_1_view.png
41_maintenance_plan_1_plan.png
42_proto_action_4_view.png
43_part_demand_4_view.png
_manifest.json
_manifest_batch2.json