# Struct migration plan — `app/parts`

Planning only. No code has been changed by this document. Grounded in
[`part_definitions_kit/model_diagram.md`](../part_definitions_kit/model_diagram.md) and the current
contents of `app/parts/control_layer/domain_structs/` and the three entrypoints that build
part-scoped views.

## 1. Current state

- `domain_structs/alias_struct.py` (`AliasStruct`) — **zero references anywhere in the app.** Dead code.
- `domain_structs/part_manufacturer_struct.py` (`PartManufacturerStruct`) — **zero references anywhere in the app.** Dead code.
- No struct loads "all aliases for a part" — the alias listing feature doesn't exist at all yet.
- No struct aggregates "which manufacturers is this part sourced from" — doesn't exist yet.
- `presentation_layer/entrypoints/revisions.py::part_revisions` hand-loops `ctx.revisions()` and calls
  `ctx.documents(rev)` / `ctx.comments(rev)` per row (15 lines of view-layer assembly).
- `presentation_layer/entrypoints/supplier_items.py::part_supplier_items` calls
  `PartThreadManager(s.item, request.user)` **directly**, duplicating exactly what
  `SupplierItemContext.documents()/comments()` already does for the single-item detail page — two
  paths to the same behavior, one of which bypasses the Context entirely.
- `presentation_layer/entrypoints/parts.py::part_detail` hand-assembles `documents` /
  `image_documents` / `other_documents` / `comments` / `supplier_items` dicts inline.

## 2. New structs

| Struct | Constructor | Role |
| :--- | :--- | :--- |
| `PartAliasIndexStruct` | `from_id(part_id, *, eager_supplier_items=False)` | All `Alias` rows for a part (`Alias.objects.filter(part=…)`, per D9's "this Part's aliases" rule). |
| `PartSourcingStruct` | `from_id(part_id, *, eager_thread=False)` | Walks `SupplierItem.objects.filter(internal_part=part)` **once**; exposes both `.supplier_items` (full list) and `.manufacturers` (deduped `PartManufacturer`s with their items grouped) from that single query pass — replaces the informal loop in `part_supplier_items` and the never-built manufacturer aggregation in one struct, rather than two structs querying `SupplierItem` twice. |
| `PartRevisionHistoryStruct` | `from_id(part_id, *, eager_thread=False)` | All `PartRevision` rows for a part; `eager_thread` toggles per-revision `documents()`/`comments()`. Distinct from the existing singular `PartRevisionStruct(revision_id)` (one-revision detail page) — no naming collision, no behavior overlap. |
| `PartDefinitionStruct` | `from_id(part_id)` | The super-struct: composes `PartStruct` + `PartRevisionHistoryStruct` + `PartSourcingStruct` eagerly (row lists only), exposes `.aliases()` / `.domains()` as **lazy** methods (query on first call) rather than always-loaded fields. |

Naming avoids reusing `AliasStruct`/`PartRevisionStruct` — those names already mean "one alias row" /
"one revision"; the part-scoped collections get distinct names (`*Index`, `*History`) so both shapes
can coexist.

## 3. Eager/lazy defaults — usage-driven, not guessed

Scanned every entrypoint that currently builds a part-scoped struct/context. Only three real call
sites exist today (`part_detail`, `part_revisions`, `part_supplier_items`) — everything else
(`revision_detail`, `supplier_item_detail`, `part_search`, `manufacturer_*`) works off a single
revision/item/manufacturer id or the bare `PartStruct`, never a part-wide aggregate.

| Slice | `part_detail` | `part_revisions` | `part_supplier_items` | Usage rate | Default |
| :--- | :---: | :---: | :---: | :--- | :--- |
| Base `Part` row | ✅ | ✅ | ✅ | 100% | always eager (base guarantee, not really a "slice") |
| Revisions — row list only | ✅ (list, no docs) | ✅ | — | 67% | **eager** |
| Revisions — per-row thread (docs/comments) | — | ✅ | — | 33%, but only 1 of the 3 sites, and it's the expensive one | **lazy** (`eager_thread=False`) — see note below |
| Part's own thread (comments/docs) | ✅ | — | — | 33% | eager only within `PartDefinitionStruct`'s own direct use (that's what `part_detail` already loads via `PartContext`) |
| Supplier items — row list only | ✅ (dict only) | — | ✅ | 67% | **eager** |
| Supplier items — per-row thread | — | — | ✅ | 33%, same shape as revisions | **lazy** |
| Manufacturers (derived) | — | — | — | 0% | **lazy** — no consumer exists yet |
| Aliases | — | — | — | 0% | **lazy** — feature doesn't exist yet |
| Domain access list | — | — | — | 0% | **lazy** — `is_domain_limited` flag reads off the base row, not this list |

**Why per-row thread nesting stays lazy despite sitting at 33% (over the 20% line):** the 20%/80%
split is a proxy for "would eager-loading this by default waste queries most of the time." Per-row
thread nesting is the expensive shape (N+1-style: one thread lookup per revision/item row), and only
one of the three real call sites wants it. Collapsing "row list" and "per-row thread" into a single
`eager=True/False` flag would force `part_detail` (which never renders per-revision documents) to pay
for that N+1 on every hit. So each slice struct gets **two independent flags**, not one:

```python
PartRevisionHistoryStruct.from_id(part_id)                        # row list eager, thread lazy (matches part_detail)
PartRevisionHistoryStruct.from_id(part_id, eager_thread=True)     # matches part_revisions' actual need
PartSourcingStruct.from_id(part_id)                                # row list eager, thread lazy
PartSourcingStruct.from_id(part_id, eager_thread=True)            # matches part_supplier_items' actual need
```

`part_revisions` and `part_supplier_items` should call their slice struct **directly** with
`eager_thread=True` rather than going through `PartDefinitionStruct` — they only ever need one slice,
deeply. `PartDefinitionStruct` is for `part_detail` and any future full-part view (export, admin JSON),
not a universal replacement for every part-related call site.

## 4. Endpoint impact once implemented

- `part_detail` — hand-assembled dict-building (parts.py:40-53) collapses to
  `PartDefinitionStruct.from_id(part_id).to_dict()`.
- `part_revisions` — the manual per-revision loop (revisions.py:44-59) collapses to
  `PartRevisionHistoryStruct.from_id(part_id, eager_thread=True).to_dict()`.
- `part_supplier_items` — drops its direct `PartThreadManager` import (supplier_items.py:23,50-54);
  uses `PartSourcingStruct.from_id(part_id, eager_thread=True)` instead, fixing the inconsistency
  where this entrypoint bypasses `SupplierItemContext`'s equivalent methods.
- Dead `AliasStruct` / `PartManufacturerStruct` get deleted, superseded by used structs.
- New capability, not just cleanup: `part_detail` can gain a "known aliases / MPNs" panel and a
  "sourced from N manufacturers" summary without new query soup, because `PartAliasIndexStruct` and
  `PartSourcingStruct.manufacturers` now exist to back them.

## 5. Open decision before implementation

None outstanding — eager defaults are usage-derived per §3. Implementation order, if/when approved:
1. `PartRevisionHistoryStruct` + wire `part_revisions` (isolated, no cross-struct dependency).
2. `PartSourcingStruct` + wire `part_supplier_items`.
3. `PartAliasIndexStruct` (net-new, no existing caller to migrate).
4. `PartDefinitionStruct` composing 1–3 + `PartStruct`, wire `part_detail`.
5. Delete `alias_struct.py` and `part_manufacturer_struct.py`.
