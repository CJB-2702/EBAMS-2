"""Screenshot the legacy Flask maintenance UI for the porting kit."""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"
OUT = pathlib.Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    # (slug, path)
    ("00_maintenance_index", "/maintenance/index"),
    ("01_manager_dashboard", "/maintenance/manager/dashboard"),
    ("02_manager_part_demands", "/maintenance/manager/part-demands"),
    ("03_part_demand_1_view", "/maintenance/part_demand/1/view"),
    ("04_part_demand_3_view", "/maintenance/part_demand/3/view"),
    ("05_manager_create_assign", "/maintenance/manager/create-assign"),
    ("06_manager_create_assign_create", "/maintenance/manager/create-assign/create"),
    ("07_manager_create_assign_unassigned", "/maintenance/manager/create-assign/unassigned"),
    ("08_manager_build_maintenance_templates", "/maintenance/manager/build-maintenance-templates"),
    ("09_maintenance_template_2_view", "/maintenance/maintenance-template/2/view"),
    ("10_maintenance_template_1_view", "/maintenance/maintenance-template/1/view"),
    ("11_view_templates", "/maintenance/view-templates"),
    ("12_proto_actions_list", "/maintenance/proto-actions/list"),
    ("13_proto_action_1_view", "/maintenance/proto-actions/1/view"),
    ("14_proto_action_create", "/maintenance/proto-actions/create"),
    ("15_manager_maintenance_plans", "/maintenance/manager/maintenance-plans"),
    ("16_maintenance_plan_3_view", "/maintenance/maintenance-plan/3/view"),
    ("17_maintenance_plan_create", "/maintenance/maintenance-plan/create"),
    ("18_maintenance_plan_3_edit", "/maintenance/maintenance-plan/3/edit"),
    ("19_maintenance_plan_3_plan", "/maintenance/maintenance-plan/3/plan"),
    ("20_technician_dashboard", "/maintenance/technician/dashboard"),
    ("21_fleet_dashboard", "/maintenance/fleet/dashboard"),
    ("22_manager_view_maintenance", "/maintenance/manager/view-maintenance"),
    ("23_manager_plan_maintenance", "/maintenance/manager/plan-maintenance"),
    ("24_manager_assign_monitor", "/maintenance/manager/assign-monitor"),
    ("25_view_events", "/maintenance/view-events"),
    ("26_event_21_view", "/maintenance/maintenance-event/21/view"),
    ("27_event_21_edit", "/maintenance/maintenance-event/21/edit"),
    ("28_event_21_work", "/maintenance/maintenance-event/21/work"),
    ("29_event_21_assign", "/maintenance/maintenance-event/21/assign"),
    ("30_event_22_view", "/maintenance/maintenance-event/22/view"),
    ("31_template_builder_drafts", "/maintenance/manager/template-builder/drafts"),
    ("32_template_builder_new", "/maintenance/manager/template-builder/new"),
    ("33_action_creator_portal_set1", "/maintenance/action-creator-portal/1"),
]

results = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = ctx.new_page()
    page.set_default_timeout(20000)

    # login
    page.goto(f"{BASE}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin987654321!")
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_load_state("networkidle")
    print("after login ->", page.url)

    for slug, path in PAGES:
        entry = {"slug": slug, "path": path}
        try:
            resp = page.goto(f"{BASE}{path}", wait_until="domcontentloaded")
            entry["status"] = resp.status if resp else None
            entry["final_url"] = page.url
            page.wait_for_timeout(1200)
            entry["title"] = page.title()
            page.screenshot(path=str(OUT / f"{slug}.png"), full_page=True)
            body = page.inner_text("body")[:400].replace("\n", " | ")
            entry["excerpt"] = body
        except Exception as exc:  # noqa: BLE001
            entry["error"] = f"{type(exc).__name__}: {exc}"
        results.append(entry)
        print(json.dumps(entry)[:300])

    browser.close()

(OUT / "_manifest.json").write_text(json.dumps(results, indent=2))
