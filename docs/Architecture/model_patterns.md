# Model patterns and rules

This document defines how Django ORM models are named, grouped, and constrained in this project. It complements [overview.md](overview.md) and [layer_rules.md](layer_rules.md).

## 1. Domain-driven grouping in `models/`

Applications often have data that should be structured or grouped by domain, not scattered arbitrarily across files.

- **Group related entities together** in the same Django app's `models/` package (as modules or subpackages). Example groupings:
  - Runtime maintenance: `maintenance_headers`, `maintenance_actions`, `action_parts`
  - Parallel template definitions: `template_maintenance_header`, `template_action`, `template_action_part`
- Prefer **separate modules** (or small subfolders) per cohesive slice so filenames reflect the domain vocabulary.
- **Mirror that grouping** in `control_layer/domain_structs/` where aggregates represent the same boundaries.

## 2. Standard columns on every table

**Every persisted table** carries:

- **Timestamps:** `created_at`, `updated_at`.
- **User tracing:** `created_by_id` and `updated_by_id` (foreign keys to the user model).

Apply these consistently unless a table is explicitly exempted (e.g. a pure join table with no meaningful audit trail — and even then, document why).

## 3. Primary keys: BigAutoField vs UUID7

- **Default:** use a **`BigAutoField` integer** primary key for most entities. It is simple, index-friendly, and works well with foreign keys inside one bounded domain.
- **When UUID7 is appropriate:** use a **UUID7** primary key when:
  - The row participates in **polymorphic or union** scenarios where the same identifier must be unique **across multiple concrete tables** without a shared sequence, or
  - You need **globally unique** references without coordination.

Document the choice in the model's docstring when it is not the default integer PK.

## 4. Auditable rows

Some models support **audit history**: a change does not only update in place; it also preserves prior state.

**Pattern:**

1. A **new row** is inserted as a **copy** of the current state, linked to a **base** record (e.g. `base_id` → the stable logical entity) and given an **audit sequence** (e.g. `audit_number` incrementing per base).
2. The **base** row (or the designated "current" row) is then **updated** to reflect the new values.

Exact column names and whether "current" lives on the base row or a pointer are project-specific; migrations and control-layer write flows enforce the invariant.

## 5. Polymorphic data and "view together" scenarios

When **separate tables** share a structural idea (e.g. "attachment link to some parent") but **different foreign-key targets** or **type defaults**, prefer **multiple concrete tables** over one overloaded table when integrity matters:

- Example: **comment attachments** vs **maintenance attachments**
  - `comment_attachments`: `linked_to_id` FK → comment; `linked_to_type` default `"comment"`.
  - `maintenance_attachments`: `linked_to_id` FK → maintenance event; `linked_to_type` default `"maintenance"`.

For rows that must be **unioned or searched in one stream**, use **UUID7** on the link or attachment entity so a union does not require a hand-rolled sequence generator shared across tables.

## 6. Abstract models for shared column sets (domain inheritance)

When several concrete models **share most of the same columns** as a domain concept — not merely "every row has audit fields" — use a Django `abstract = True` model in its own module (e.g. `VirtualAction`) that holds those shared fields.

Examples where this applies:

- `MaintenanceAction`, `TemplateMaintenanceAction`, `PrototypeAction` — all are "actions" with the same core shape.

**Requirements:**

- Put shared fields only on the abstract base; concrete models add table-specific fields and `Meta.db_table` as needed.
- Add a class method `get_base_columns()` on the abstract model that returns the set of field names shared by all subclasses.

**Distinction from generic mixins:**

| Mechanism | Purpose |
| :--- | :--- |
| **User/audit mixins** (e.g. `CreatedUpdatedByMixin`) | Cross-cutting **technical** concerns applied to many unrelated tables. |
| **Auditable pattern** (section 4) | **Generic** pattern for history/versioning where required. |
| **`abstract` domain base** (e.g. `VirtualActionItem`) | **Domain-driven** shared shape: "these three tables are the same kind of thing with different roles." |

Use abstract bases when the **business meaning** is shared, not only because two tables both have `created_at`.

## 7. No business logic on model classes

**Model modules define schema, constraints, and declarative metadata only.** They must not contain business rules, orchestration, or workflows. Validation that encodes domain policy beyond DB-level constraints lives in the control layer or explicit validators used from there.

**Exception:** Only when a human maintainer marks it explicitly in the model or method docstring:

```text
# DELIBERATE ANTI-PATTERN
```

Describe **why** the exception exists. Unmarked logic on the model is not an acceptable default.

---

Together with [overview.md](overview.md) (models may not import the control layer or presentation layer), these rules keep persistence **honest and boring**: structure and integrity in `models/`, behavior in `control_layer/` and tests.
