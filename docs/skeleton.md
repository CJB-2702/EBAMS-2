# Context Skeleton

Machine-maintainable index of every doc file under `docs/`, grouped by tier. See [Context_Scaling/skeleton_spec.md](Context_Scaling/skeleton_spec.md) for the rules. The docs crawler is the **only** mechanism that should rewrite this file — keep manual edits limited to one-line description tweaks if a heading changes.

## Tier 0
- Claude.md — Application router, identity, global rules, persona command map. (Lives at project root, not under `docs/`.)

## Tier 1
- docs/skeleton.md — This file. Full index of all context files.
- docs/Context_Scaling.md — Context scaling framework: tier table, reference directionality rule.
- docs/Architecture.md — Layered architecture, OOP control patterns, model and endpoint rules.
- docs/UX_UI.md — Visual language, density contract, HTMX paradigms, layout rules.
- docs/Authorization.md — Two-gate access model (capability + scope).
- docs/CoreDomain.md — Shared business entities and the domain/organization/division hierarchy.
- docs/Events.md — Events sub-application: comments, files, shadow history, contexts.
- docs/Development_Tools.md — Dev workflow, DB rebuild, environment generation, seeded users.
- docs/ApplicationGoals.md — Product vision and user-centric objectives.
- docs/technical_decisions.md — Rolling summary of locked decisions, active tech debt, incident takeaways.
- docs/applications.md — Convention for sub-application docs; which apps stay at Tier 1/2 and why.

## Tier 2

### Context_Scaling/
- docs/Context_Scaling/tier_reference.md — Detailed per-tier descriptions and Key Files inventories.
- docs/Context_Scaling/persona_routing.md — Persona slash command routing rules.
- docs/Context_Scaling/tools_and_scripts.md — Codebase mapping script and docs crawler spec.
- docs/Context_Scaling/technical_decisions_system.md — Technical decisions folder structure and entry format.
- docs/Context_Scaling/skeleton_spec.md — This file's own rules and structure template.
- docs/Context_Scaling/domain_skeleton_bundles_spec.md — Domain skeleton bundle format and naming convention.
- docs/Context_Scaling/refactoring_guide.md — Drift smells and post-session context synthesis.

### Architecture/
- docs/Architecture/overview.md — Sub-app folder layout and layer responsibilities.
- docs/Architecture/layer_rules.md — Reads vs writes; what may run in an entrypoint.
- docs/Architecture/oop_control_patterns.md — Class-suffix vocabulary and the new-feature playbook.
- docs/Architecture/model_patterns.md — Model naming, audit columns, abstract bases, PK choice.
- docs/Architecture/endpoint_patterns.md — OOP endpoint design, collection vs detail, `format=` contract.
- docs/Architecture/htmx_patterns.md — HTMX conventions, F5 rule, CSRF, `hx-select` defaults, session drafts.
- docs/Architecture/seeding.md — Fixture placement, audit-field handling, prod policy.
- docs/Architecture/standards.md — Engineering principles and stack choices.
- docs/Architecture/tests.md — Testing conventions.
- docs/Architecture/skeleton_instructions.md — Scan targets for backend service / handler / context tasks.

### UX_UI/
- docs/UX_UI/visual_language.md — Tokens, sharp corners, dark-mode strategy.
- docs/UX_UI/page_structure.md — Page shell, hero, sidebars, stat bars, portal patterns.
- docs/UX_UI/format_contract.md — `format=` density contract and HTMX fragment variants.
- docs/UX_UI/form_style_guide.md — Card-footer geometry, primary/secondary slot rules, inline forms.
- docs/UX_UI/multi_step_flows.md — Multi-step flows, session-backed drafts, namespaced state.
- docs/UX_UI/modals.md — Native `<dialog>` + Bulma card modals; `commandfor`/`command`.
- docs/UX_UI/tabs.md — Allowable tab strategies: HTMX vs web component vs static.
- docs/UX_UI/common_buttons.md — Standard buttons, icon set, semantic colors, table-row rules.
- docs/UX_UI/dual_listbox.md — Dual listbox: when, anatomy, session-staged commit.
- docs/UX_UI/searchbars.md — `<search-dropdown>` picker vs plain HTMX list filter.
- docs/UX_UI/pagination.md — Pagination and shared partials.
- docs/UX_UI/accessibility.md — Accessibility baseline.
- docs/UX_UI/skeleton_instructions.md — Scan targets for frontend Bulma + HTMX tasks.

### Authorization/
- docs/Authorization/architecture_summary.md — One-page architectural summary of both gates.
- docs/Authorization/architecture_decisions.md — Design trade-offs and accepted risks.
- docs/Authorization/rbac.md — Django permissions, permission groups, what Django auth covers.
- docs/Authorization/data_ownership.md — The Data Domain primitive, the Golden Rule, admin warning system.
- docs/Authorization/users.md — User model concerns: assignments, session snapshot, audit FKs.
- docs/Authorization/roles_concept.md — Roles: business concept and rules.
- docs/Authorization/roles_decisions.md — Roles: design decisions and rationale.
- docs/Authorization/roles_examples.md — Roles: common assignment scenarios.
- docs/Authorization/domain_templates_concept.md — Domain templates: business concept and rules.
- docs/Authorization/domain_templates_models_plan.md — Domain templates: architectural plan.
- docs/Authorization/password_policy.md — OWASP-aligned password policy.
- docs/Authorization/data_access_exceptions.md — Hand-maintained log of routes that deviate from the Golden Rule.

### CoreDomain/
- docs/CoreDomain/core_models.md — Entity dependency graph, must-have edges, link-table strategy.
- docs/CoreDomain/divisions.md — Division → Organization → Domain map.

### Events/
- docs/Events/events.md — Models, mixins, status/priority choices, permissions, domain scoping.
- docs/Events/event_context_design.md — Structs and contexts: `BaseEventStruct`, `EventContext`, `CommentContext`.
- docs/Events/events_endpoints.md — Endpoint-by-endpoint routing: when to call a handler vs a context.
- docs/Events/comment_auditing.md — Comment edit, delete, attachment, and file lifecycle invariants.
- docs/Events/pk_hashing_migration.md — Slug → hashid migration plan and entrypoint pattern.

### Development_Tools/
- docs/Development_Tools/db_rebuild.md — Full DB reset workflow.
- docs/Development_Tools/env_generation.md — `.env` generation, secret material, dev vs prod defaults.
- docs/Development_Tools/users_and_passwords.md — Seeded user accounts, default passwords, environment overrides.
- docs/Development_Tools/seed_dev.md — `seed_dev` command, fixture vs imperative seed boundaries.

### technical_decisions/
- docs/technical_decisions/README.md — Folder structure overview.
- docs/technical_decisions/history/2026-04-rename-ownership-to-domain.md — Data-scope primitive rename.
- docs/technical_decisions/history/2026-05-htmx-driven-tabs.md — Tabs default to HTMX-driven `?view=` pattern.
- docs/technical_decisions/history/2026-05-dual-listbox-htmx-light-dom.md — Dual listbox HTMX-first migration.
- docs/technical_decisions/tech_debt/administration_application.md — Departments layer + data-access exceptions rule.
- docs/technical_decisions/tech_debt/dual_listbox_migration_plan.md — Templates pending migration to the new pattern.
- docs/technical_decisions/tech_debt/carbon_colors_incomplete_migration.md — Event detail depth system unfinished.
- docs/technical_decisions/incident_history/2026-05-web_component_tab_incident.md — Why custom-element tabs were abandoned.

### domain_skeleton_bundles/
- docs/domain_skeleton_bundles/README.md — Index of available bundles.
- docs/domain_skeleton_bundles/domain_service_skeleton_instructions.md — Backend service / handler / context work.
- docs/domain_skeleton_bundles/ui_skeleton_instructions.md — Frontend Bulma + HTMX work.
- docs/domain_skeleton_bundles/rbac_skeleton_instructions.md — RBAC / permission / role / domain template changes.
- docs/domain_skeleton_bundles/events_integration_skeleton_instructions.md — Integrating another sub-app with events.

## Tier 3

### Architecture/Examples/
- docs/Architecture/Examples/sub_application_tree.md — Canonical sub-application folder tree.
- docs/Architecture/Examples/read_vs_write_examples.md — Allowed and not-allowed entrypoint shapes.
- docs/Architecture/Examples/control_layer_class_skeletons.md — Concrete Struct, Context, Handler, Manager, Guard, Factory shapes.
- docs/Architecture/Examples/htmx_csrf_and_search_snippets.md — Base-template CSRF hook and search-fragment markup.

### UX_UI/Examples/
- docs/UX_UI/Examples/page_hero_markup.md — Canonical page-hero HTML.
- docs/UX_UI/Examples/card_footer_markup.md — Canonical card-footer markup for several common cases.
- docs/UX_UI/Examples/button_markup.md — Canonical Save / Cancel / Delete / Edit / Refresh / table-row markup.
- docs/UX_UI/Examples/dual_listbox_markup.md — Fragment template, endpoint response shape, side-effect pattern.
- docs/UX_UI/Examples/search_dropdown_component.md — `<search-dropdown>` usage and source behaviours.
