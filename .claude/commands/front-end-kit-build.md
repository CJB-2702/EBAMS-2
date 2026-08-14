---
description: Build the throwaway Flask stager for an already-staged front-end kit — a clickable mockup of the planned routes for visual and flow validation.
argument-hint: "<topic> — an existing front-end-kit/<topic>/ folder (e.g. parts)"
---

Read [.claude/agents/front-end-kit.md](.claude/agents/front-end-kit.md) and [harness/front_end_kit_process/how_to_build_the_flask_stager.md](harness/front_end_kit_process/how_to_build_the_flask_stager.md), then build the Flask stager for `front-end-kit/$1/`.

Use this when the front-end kit documents were staged earlier and you decided to skip the mockup at the time — or answered "straight to integration" and changed your mind.

## Preconditions — check these first, and stop if either fails

1. `front-end-kit/$1/` exists with `route_skeleton.md`, `navigation_map.md`, and `workflows.md` present.
2. **Both gates are PASS** in the kit README:
   - Navigation reachability — mocking an unreachable page teaches nothing.
   - Workflow review — otherwise you will mock a form that should have been a wizard.

Report the failure and stop rather than building against a failed gate.

## What to build

`front-end-kit/$1/stager/` — a Flask app with no backend logic whatsoever.

- **One route per route-skeleton entry**, at the same paths, so URL structure is validated too.
- **Every navigation edge clickable.** A stager with dead links validates nothing — this is the primary thing you built it to check.
- **The project's real styling** — Bulma theme layer, sharp corners, actual markup copied from [harness/UX_UI/index.md](harness/UX_UI/index.md) (components, navigation, search, file_management, and design_patterns guides). Not an approximation.
- **Wizards at full scroll length**, every card in order, later cards visibly disabled.
- **Empty states rendered** for at least one instance of each card — cards always render in this project.
- **Dummy data only** — hardcoded dicts in `dummy_data.py`. No DB, no ORM, no real validation.

## What to report back

How many routes were staged, which were skipped and why, and which specific flows are worth clicking through first.

## Remember

The stager is disposable, and so is the kit around it. Its purpose is to be looked at and thrown away.
