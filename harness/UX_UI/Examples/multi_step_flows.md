---
type: "UX Guide"
title: "Multi-step flows"
description: "Drafts live under a namespaced dictionary in request.session specific to the feature."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Multi-step flows

**Portals vs steps:** a **portal** is a whole area of the app (events, restocking, etc.). Inside one portal, a **guided flow** is implemented as **one create (or edit) page**, not a chain of different pages for each step.

- Prefer **one route** (for example `…/events/create`) with **vertical scroll** and **all steps on the same document**.
- **Later steps** are **shown** (headings, cards, or sections) but **disabled** (non-interactive fields, `disabled` / `aria-disabled`, or server-side omission of POST handlers) until prior steps pass validation.
- **Final submission** is available only when every step is complete.
- Persist step and draft field state in **session** (namespaced) — see the session-draft pattern below.

**Do not** model "step 1 of 3" as three separate URLs for the same draft resource unless there is an exceptional reason (bookmarking deep steps, very heavy server work per step). The default pattern is visibility + progressive enablement on **one** page.

---

## When a create page becomes a multi-card wizard

The trigger is structural, not aesthetic:

> A create or edit page is a **multi-card wizard** when the entity has **more than one reverse foreign key** that a user would plausibly populate in the same sitting.

One reverse FK is a form with a section. Two or more — manufacturers *and* revisions *and* notes on a part; tasks *and* parts *and* assignees on a maintenance activity — is a wizard. Each of those relations becomes its own card in the vertical scroll.

Secondary signals that push a borderline page toward wizard: a file upload, a status that must be set at creation, or a related record the user may need to create inline.

**Each assignment relation gets its own card, in the page.** Use the left-heavy assignment card pair ([../Examples/left_heavy_assignment_card_pair.md](../Examples/left_heavy_assignment_card_pair.md)) or a dual listbox ([dual_listbox.md](dual_listbox.md)) — never a modal. See [modals.md](modals.md) for why.

Card order follows dependency: identity fields first, then relations that depend on them, then free-form attachments and notes.

---

## The session-draft pattern

Drafts live under a namespaced dictionary in `request.session` specific to the feature. Example:

```python
request.session['event_draft'] = {
    'assigned_users': [1, 5, 12],
    'temp_title': "Project EBAMS Launch"
}
request.session.modified = True
```

- **No DB commit** until the user clicks the final submit.
- **HTMX POST** to a specialised session-update endpoint updates the dict; the response is a full-page refresh or an HTMX-triggered fetch of the same `/events/create` URL.
- **Template logic** reads the dict to render sub-fields (e.g. "assigned user" rows) as if they were saved.
- **Finalisation:** the create entrypoint pulls data from `request.session['event_draft']`, calls a control-layer factory in one transaction, then `del request.session['event_draft']`.

This keeps the F5 rule honest — refreshing the page restores the staged draft.

---

## When a single-scroll page is too much

Two narrow exceptions justify splitting a draft across multiple URLs:

1. **The user is expected to bookmark a deep step.** For example a long onboarding wizard where a sales rep returns days later to step 4.
2. **Per-step server work is genuinely heavy.** For example uploading and processing a large CSV before later steps even make sense.

In both cases, document the exception in the relevant entrypoint and keep the session-draft pattern; the URLs are surface, the draft state is still server-side and namespaced.

---

## Common mistakes

- **Splitting steps across `/create/step-1`, `/create/step-2`** without an exceptional reason — inconsistent back/forward and session handling.
- **JavaScript-only step disabling.** Step gates are server-side; without that, the F5 rule fails on refresh.
- **Forgetting `request.session.modified = True`** after mutating a nested dict — Django won't save the change.
- **Leaving the draft after final commit.** Always `del` the namespaced key once the workflow completes.
