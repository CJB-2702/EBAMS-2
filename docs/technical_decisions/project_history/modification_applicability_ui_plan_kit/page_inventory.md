# Page Inventory — Classified

Per [`docs/starter_kit_process/how_to_plan_ui_features.md`](../docs/starter_kit_process/how_to_plan_ui_features.md),
every surface is classified and given a primary goal.

- **Navigation Page** — hubs/lists that orient and route.
- **User View** — read-only displays of information.
- **Work Portal** — action-oriented forms / workflows.

Most surfaces here are **extensions** of pages the assets mock already serves
(a new card, a new column, a new sub-route), not brand-new top-level pages. The one
genuinely new screen is the **Applicability Editor** — the centerpiece, reused across
both phases.

Legend: **P1** = Phase 1 (modification applicability, control already built) ·
**P2** = Phase 2 (template applicability, control planned).

---

## Navigation Pages

| Page | Phase | Goal |
| :--- | :--- | :--- |
| **Defined Modifications List** (`/assets/configurations/modifications/`) | P1 | *Existing page, extended.* Add a **Mode** tag column and an **applicability filter** so a catalog manager can see at a glance which modifications are restricted and how. |
| **Config Templates List** (`/assets/configurations/templates/`) | P2 | *Existing page, extended.* Same Mode tag column + filter for templates. |

## User Views

| Page | Phase | Goal |
| :--- | :--- | :--- |
| **Modification Applicability Card** (on `modification_detail`) | P1 | The read view of one modification's applicability: the mode, the **binding** list(s), the **derived** classes (in `MODEL_SET`), and the **suggestion** lists — each visually distinct. Includes the "Applies to" plain-language summary. |
| **Template Applicability Card** (on `template_detail`) | P2 | Same card, for a template. Plus a **per-modification compatibility** strip showing which member mods are provably compatible with the template's reach. |
| **Asset "why blocked" helptext** (on `asset_configuration_edit`) | P1 | Surfaces `ApplicabilityPolicy.explain(...)` as the reason a modification is unavailable for *this* asset. |
| **Current Configuration applicability note** (Asset-360 / `asset_configuration_detail`) | P1 | A small badge confirming each applied modification was permitted for the asset (audit reassurance). |

## Work Portals

| Page | Phase | Goal |
| :--- | :--- | :--- |
| **Applicability Editor — Modification** (`/assets/configurations/modifications/<id>/applicability/`) | P1 | **The centerpiece.** Set the mode and author the class/model allow-lists with mode-correct behavior: dual-listbox panels, `MODEL_SET` auto-derive (read-only classes), `STRICT` dead-model guard (inline rejection), suggestion labelling, and a live "Applies to" preview. |
| **Applicability Editor — Template** (`/assets/configurations/templates/<id>/applicability/`) | P2 | The **same editor component**, bound to a template. Default `MODEL_SET` seeded with the template's own model (reproduces today's single-model assignment gate). |
| **Gated Modification Picker** (within `asset_configuration_edit`) | P1 | The apply-to-asset workflow: the "available modifications" list **disables** rows the asset's class/model forbids, each with the policy reason; only permitted mods can be added. |
| **Template Builder — compatibility guard** (within `config_template_builder`) | P2 | When a modification is added to a template, run the **provable-conflict** check; block a provably-incompatible add with the reason, allow-but-warn the undecidable. |
| **Mode quick-set** (inline on `modification_detail` / `template_detail`) | P1/P2 | A lightweight HTMX control to flip the mode without opening the full editor (normalizes lists per the transition rules). |

---

## Fragment inventory (HTMX partials, not separate routes)

The editor is a **composition of fragments** swapped by mode, mirroring how the
Asset-360 page composes cards. These are not their own routes but must be built to
convey the feel. See [navigation_flow.md](navigation_flow.md#applicability-editor-anatomy).

| Host page | Fragments |
| :--- | :--- |
| Applicability Editor | Mode selector · Class panel (editable / read-only-derived / muted-suggestion) · Model panel (editable / muted-suggestion) · Dead-model inline error · "Applies to" preview (sample assets pass/fail) |
| Modification / Template detail | Applicability card (view) · Mode quick-set · "Edit applicability" launcher |
| Asset Configuration Edit | Gated available-mods list · disabled-row reason tooltip |

## Out of scope (explicitly)

- **Modification / template CRUD** (name, code, category, children, etc.) — already
  built in the assets mock; this kit only adds the applicability surfaces.
- **RBAC / ownership scoping** of who may author applicability — deferred (matches the
  control kit, which left RBAC out of Phase 1/2).
- **Search-by-applicability across assets** ("which assets can take this mod") beyond the
  editor's sample preview — a possible later page, noted but not planned here.
