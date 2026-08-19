"""Second batch: template builder + remaining legacy maintenance pages."""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"
OUT = pathlib.Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("34_template_builder_1_edit", "/maintenance/manager/template-builder/1"),
    ("35_template_builder_1_action_creator", "/maintenance/manager/template-builder/1/action-creator-portal"),
    ("36_event_22_edit", "/maintenance/maintenance-event/22/edit"),
    ("37_event_22_work", "/maintenance/maintenance-event/22/work"),
    ("38_event_22_assign", "/maintenance/maintenance-event/22/assign"),
    ("39_technician_most_recent_event", "/maintenance/technician/most-recent-event"),
    ("40_maintenance_plan_1_view", "/maintenance/maintenance-plan/1/view"),
    ("41_maintenance_plan_1_plan", "/maintenance/maintenance-plan/1/plan"),
    ("42_proto_action_4_view", "/maintenance/proto-actions/4/view"),
    ("43_part_demand_4_view", "/maintenance/part_demand/4/view"),
]

results = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = ctx.new_page()
    page.set_default_timeout(20000)
    page.goto(f"{BASE}/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin987654321!")
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_load_state("networkidle")

    for slug, path in PAGES:
        entry = {"slug": slug, "path": path}
        try:
            resp = page.goto(f"{BASE}{path}", wait_until="domcontentloaded")
            entry["status"] = resp.status if resp else None
            entry["final_url"] = page.url
            page.wait_for_timeout(1200)
            entry["title"] = page.title()
            page.screenshot(path=str(OUT / f"{slug}.png"), full_page=True)
            entry["excerpt"] = page.inner_text("body")[:300].replace("\n", " | ")
        except Exception as exc:  # noqa: BLE001
            entry["error"] = f"{type(exc).__name__}: {exc}"
        results.append(entry)
        print(json.dumps(entry)[:260])
    browser.close()

(OUT / "_manifest_batch2.json").write_text(json.dumps(results, indent=2))
