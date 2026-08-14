---
type: "Process Guide"
title: "How to Build the Flask Stager"
description: "You are acting as a Frontend Prototyping Agent. Build an optional clickable Flask mockup of the planned routes for visual and flow validation before Django work begins."
tags: [front-end-kit-process, process-guide, optional]
context_tier: 2
---

# How to Build the Flask Stager

**Role & Objective:**
You are acting as a Frontend Prototyping Agent. Build a lightweight, clickable Flask prototype of the routes in `route_skeleton.md`, strictly for visual and flow validation before any Django implementation.

---

## This stage is optional and must be asked for

**Never build the stager without asking.** After the kit's documents are staged and both gates pass, ask the developer:

> Flask mockup, or straight to integration?

Both answers are normal. Going straight to integration means the docs *are* the deliverable and `/frontend-persona` builds directly against them in Django.

The stager earns its cost when the developer wants to *feel* the navigation and wizard scroll before committing to templates — typically for a large or unfamiliar workflow. It is waste when the pages are routine.

The stager can also be built later, against an already-staged kit, with `/front-end-kit-build <topic>`.

---

## Prerequisites

Do not start until:

- `navigation_map.md` gate is **PASS** — a mockup of an unreachable page teaches nothing.
- `workflows.md` gate is **PASS** — otherwise you will mock a form that should have been a wizard.

If either fails, say so and stop.

---

## Instructions

1. **No backend logic.** No database, no ORM, no models, no real validation. Hardcode dictionaries and lists in `app.py` or a `dummy_data.py` module.

2. **One route per route-skeleton entry.** Same paths, so the URL structure is validated too, not just the visuals. `Action`-type entries (POST-only, no page) get a stub route that flashes a message and redirects.

3. **Every navigation edge must work.** This is the point of the exercise. Every link in `navigation_map.md` is clickable and lands somewhere real. A stager with dead links validates nothing.

4. **Use the project's real styling.** Bulma with the project theme layer, sharp corners, the actual component markup from [../UX_UI/index.md](../UX_UI/index.md) (components, navigation, search, file_management, and design_patterns guides). Copy the markup — do not approximate it. The stager's value is that it looks like the app; a generic mockup answers no question worth asking.

5. **Render wizards at full scroll length.** Every card, in order, with realistic dummy content. Show the progressive-enablement states — disabled later cards — even though the gating is faked. Feeling the scroll length *is* the deliverable for a wizard.

6. **Fake the interactions honestly.** Assignment cards move items client-side; forms submit to a stub route that flashes success and redirects. Do not wire real persistence, but do not leave buttons inert either — an inert button hides the flow question you built this to answer.

7. **Show empty states.** For at least one instance of each card, render the empty state from `route_skeleton.md`. Cards always render in this project; the stager must demonstrate that they look right when empty.

8. **Do not build a Django app.** The stager is disposable and lives outside the application. Its purpose is to be thrown away.

---

## Output location

```
front-end-kit/<topic>/stager/
  app.py
  dummy_data.py
  requirements.txt        # flask only
  README.md               # how to run it, what it does and does not do
  static/
  templates/
    base.html
    <one per route>
```

Run instructions in the stager's `README.md` must be a single copy-pasteable block, and must state plainly that this is a throwaway mockup with no backend.

---

## Example Scenario: Asset Management Application

*Concept:* Tracking vehicles and assignments.

- `@app.route('/fleet')` renders `fleet.html` from a hardcoded list of vehicle dicts, with working links into `/vehicles` and `/vehicles/<id>`.
- `@app.route('/vehicles/create')` renders the full four-card wizard at real scroll length, the assignment card populated from a dummy manufacturer pool, later cards visibly disabled.
- `@app.route('/vehicles/<id>/reassign', methods=['POST'])` flashes "Vehicle reassigned (mock)" and redirects to the detail page.

---

## Required Output Format

The stager itself, written to `front-end-kit/<topic>/stager/`, runnable with `pip install -r requirements.txt && python app.py`.

Then report back to the developer: how many routes were staged, which were skipped and why, and which specific flows are worth clicking through first.
