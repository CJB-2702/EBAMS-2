# Technical Decisions — Tier 1 Anchor

This file is the **rolling summary** of locked engineering decisions, active tech debt, and incident takeaways. It is short by design — at most 1–2 pages. The sub-folders under `technical_decisions/` hold the per-event detail; this file distils the parts that must remain in working context.

Format and folder structure are specified in [Context_Scaling/technical_decisions_system.md](Context_Scaling/technical_decisions_system.md).

---

## Locked decisions (hard constraints — do not relitigate)

- **Tabs default to HTMX-driven, one URL with `?view=`.** Web-component tab attempts failed three times due to `connectedCallback` firing before child nodes are parsed. The HTMX-driven pattern is the canonical solution for any non-trivial tabbed page. Detail: [technical_decisions/history/2026-05-htmx-driven-tabs.md](technical_decisions/history/2026-05-htmx-driven-tabs.md).
- **Dual listbox uses HTMX-first light-DOM components with toast alerts.** Replaced the old form-submission + page-reload model. New components live at `app/static/web_components/dual_listbox.js` and `list_box.js`. Detail: [technical_decisions/history/2026-05-dual-listbox-htmx-light-dom.md](technical_decisions/history/2026-05-dual-listbox-htmx-light-dom.md).
- **"Ownership group" renamed to "Data Domain" (or "Domain").** The old name overloaded the word "group" with `auth.Group`. The data-scope primitive is now `Domain`; permission groups keep the Django-permission meaning exclusively. Detail: [technical_decisions/history/2026-04-rename-ownership-to-domain.md](technical_decisions/history/2026-04-rename-ownership-to-domain.md).
- **URLs use hashids on integer PKs for events and comments.** Slug fields are removed. Files and attachments keep UUID7. Decoding is an entrypoint concern; the control layer never sees hashids. Detail: [Events/pk_hashing_migration.md](Events/pk_hashing_migration.md).
- **Sharp corners everywhere.** All Bulma radius variables pinned to zero. No pills, no rounded cards, no per-component exceptions.
- **No business logic on models.** Schema and constraints only. Intentional exceptions are marked `# DELIBERATE ANTI-PATTERN` with context.

---

## Active tech debt (work known, deferred)

- **Administration application — departments layer.** A `Departments` model is likely needed between organizations and domains. Data-access exceptions probably need to become a `.claude` rule. Detail: [technical_decisions/tech_debt/administration_application.md](technical_decisions/tech_debt/administration_application.md).
- **Dual listbox migration not yet complete.** Several detail templates (organizations, divisions, domains, roles, permission groups) still use the old form-submission pattern. Plan and checklist: [technical_decisions/tech_debt/dual_listbox_migration_plan.md](technical_decisions/tech_debt/dual_listbox_migration_plan.md).
- **Carbon Colors migration incomplete.** Event detail page card styling / depth system still half-migrated. Detail: [technical_decisions/tech_debt/carbon_colors_incomplete_migration.md](technical_decisions/tech_debt/carbon_colors_incomplete_migration.md).

---

## Recent incidents (what failed, what changed)

- **Web Component tab incident (2026-05).** Three iterations of custom-element tab switchers failed because `connectedCallback` fires on the opening tag, before child `<li>` panels are parsed. Compounded by custom-element names not being parser scoping boundaries — inner `<li>`s closed outer tab-panel `<li>`s. Resolved by adopting HTMX-driven tabs and `<ul data-slot="...">` for slotted list data. Detail: [technical_decisions/incident_history/2026-05-web_component_tab_incident.md](technical_decisions/incident_history/2026-05-web_component_tab_incident.md).

---

## Reference directionality

This anchor references **only** files inside `technical_decisions/` and (where a decision has its detail in a domain folder) the relevant Tier 2 file in that folder. Per-event detail must not be inlined here; if a decision needs more than two sentences of context, the body lives in `technical_decisions/history/<file>.md` and this anchor summarises and links it.
