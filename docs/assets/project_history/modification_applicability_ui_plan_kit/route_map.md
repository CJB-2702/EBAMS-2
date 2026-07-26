---
type: "Technical Decision"
title: "Route Map — Applicability Pages ↔ Existing Pages ↔ Control Wire-Points"
description: "The headline deliverable."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-ui-plan-kit]
context_tier: 2
---

# Route Map — Applicability Pages ↔ Existing Pages ↔ Control Wire-Points

The headline deliverable. Every surface this kit adds, mapped to the **existing
assets-mock page it extends**, the **real control object** it will eventually wire to,
and its classification (`Nav` = Navigation, `UV` = User View, `WP` = Work Portal).

**URL prefix:** `/assets/` ([`app/assets/urls.py`](../app/assets/urls.py), already
included in [`app/config/urls.py`](../app/config/urls.py)). New URL names are prefixed
`modification_applicability_*` / `template_applicability_*`.

**Existing config entrypoints** (all in
[`app/assets/presentation_layer/entrypoints/configurations.py`](../app/assets/presentation_layer/entrypoints/configurations.py)):
`defined_modification_index/detail/create`, `config_template_index/builder/detail`,
`asset_configuration_detail/edit`.

Legend for **Kind**: **New route** · **New sub-route** · **Extend page** (card/column on
an existing route) · **Extend fragment** (HTMX partial within an existing page).

---

## Phase 1 — Modification Applicability *(control layer already built)*

| # | Surface | Route / host | URL name | Extends (existing) | Kind | Real wire-point | Class |
| :-- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Applicability Editor — Modification** | `/assets/configurations/modifications/<id>/applicability/` | `modification_applicability_edit` | `modification_detail` | New sub-route | `ModificationApplicabilityManager.set_mode / add_class / remove_class / add_model / remove_model` | WP |
| 2 | Applicability **card** (read) | on `…/modifications/<id>/` | — | `modification_detail` | Extend page | `ModificationApplicabilityManager.struct(mod)` → `ApplicabilityStruct` | UV |
| 3 | **Mode quick-set** | fragment on `modification_detail` | `modification_applicability_set_mode` | `modification_detail` | Extend fragment | `ModificationApplicabilityManager.set_mode` | WP |
| 4 | **"Applies to" preview** | fragment in editor (1) | `modification_applicability_preview` | — (new, inside editor) | Extend fragment | `ApplicabilityPolicy.is_allowed` over sample assets | UV |
| 5 | **Mode tag column + filter** | `/assets/configurations/modifications/` | (same `defined_modification_index`) | `defined_modification_index` | Extend page | read `mod.applicability_mode` | Nav/UV |
| 6 | **Gated modification picker** | within `…/assets/<id>/configuration/edit/` | (same `asset_configuration_edit`) | `asset_configuration_edit` | Extend page | `ModificationApplicabilityValidator.check(asset, mod)` per candidate | WP |
| 7 | **"Why blocked" helptext** | fragment on gated picker (6) | — | `asset_configuration_edit` | Extend fragment | `ApplicabilityPolicy.explain(...)` | UV |
| 8 | **Applied-mod permitted badge** | on `…/assets/<id>/configuration/` & Asset-360 config card | — | `asset_configuration_detail` | Extend page | derived at apply time (already gated) | UV |

## Phase 2 — Template Applicability *(control layer planned)*

| # | Surface | Route / host | URL name | Extends (existing) | Kind | Real wire-point | Class |
| :-- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 9 | **Applicability Editor — Template** | `/assets/configurations/templates/<id>/applicability/` | `template_applicability_edit` | `config_template_detail` | New sub-route | `TemplateApplicabilityManager.*` (reuses shared `ApplicabilityPolicy` / `ApplicabilitySyncHandler`) | WP |
| 10 | Template applicability **card** (read) | on `…/templates/<id>/` | — | `config_template_detail` | Extend page | `TemplateApplicabilityManager.struct(template)` | UV |
| 11 | **Builder applicability section** | within `…/templates/builder/` | (same `config_template_builder`) | `config_template_builder` | Extend page | template default `MODEL_SET` seeded with its model (kit D7) | WP |
| 12 | **Compatibility guard** (add mod → template) | fragment in builder (11) | `template_modification_compat_check` | `config_template_builder` | Extend fragment | `ApplicabilityCompatibilityPolicy.can_add(template, mod)` (Phase 2 control) | WP |
| 13 | **Per-mod compatibility strip** | on `template_detail` | — | `config_template_detail` | Extend page | `ApplicabilityCompatibilityPolicy` over member mods | UV |
| 14 | **Mode tag column + filter** | `/assets/configurations/templates/` | (same `config_template_index`) | `config_template_index` | Extend page | read `template.applicability_mode` | Nav/UV |

---

## The reused component

Surfaces **1** and **9** are the **same Django template + HTMX behavior** parameterized
by entity ("modification" vs "template"). This mirrors the control kit's design, where
`ApplicabilityStruct` / `ApplicabilityPolicy` / `ApplicabilitySyncHandler` are
entity-agnostic and shared. Build it once in Phase 1; Phase 2 only adds the template
binding + the compatibility guard.

## Count summary

| Group | Surfaces |
| :--- | ---: |
| Phase 1 — Modification | 8 |
| Phase 2 — Template | 6 |
| **Total** | **14** |
| of which **new routes** | **2** (the two editors) |
| of which **extensions** of existing pages | **12** |

> Because 12 of 14 surfaces extend pages that already exist in the assets mock, this is a
> **small, additive** build — not a new app section. The risk and review surface concentrate
> in the one new component: the Applicability Editor.
