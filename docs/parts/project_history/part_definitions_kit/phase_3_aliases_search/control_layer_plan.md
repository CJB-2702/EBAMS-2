# Phase 3 — Control Layer Plan: Aliases & Unified Search

Suffix vocabulary per
[`OOP_CONTROL_PATTERNS`](../../harness/Architecture/OOP_CONTROL_PATTERNS.md). Home:
`app/parts/control_layer/` (write/resolve) and `app/parts/presentation_layer/search/`
(`PartSearch`). This phase wires the auto-population seams left in Phases 1–2.

---

## `AliasStruct` — read model

`domain_structs/alias_struct.py`.

```
AliasStruct(alias, resolved_part)
  .to_dict() -> dict   # {alias, alias_type, association_type, source,
                       #  resolved_part:{id, part_number, name}}
```

---

## `AliasFactory` — the single alias write path

`factories/alias_factory.py`. Class methods only; the **only** creator of aliases, so the
`association_type`/secondary-FK rule and normalization live in one place. Every alias gets a
**primary `part`** ([D9](../decisions.md)); the factory method picks the `association_type`.

```
AliasFactory.for_string(part, alias, alias_type, *, source, actor) -> Alias        # PART_TO_STRING
AliasFactory.for_vendor_item(part, item, alias, alias_type, *, source, actor) -> Alias  # PART_TO_VENDOR_ITEM
AliasFactory.for_alternate_part(part, alternate_part, alias, alias_type, *, source, actor) -> Alias  # PART_TO_PART
```

- Normalizes `alias` → `normalized_value` (case/whitespace fold).
- Sets `association_type` and the matching secondary FK; enforces the typed-link rule before insert
  (defense in depth alongside the DB CheckConstraint, [D9](../decisions.md)).
- `alias_type` is a free business-source label (open set); `association_type` is the closed 3-value enum.
- `AliasValidator` rejects empty values and duplicate `(alias_type, normalized_value)` per the
  uniqueness rule chosen at review.

---

## Orchestrators — auto-population (fill the Phase 1/2 hooks, [D8](../decisions.md))

`orchestrators/part_alias_orchestrator.py`, `orchestrators/supplier_alias_orchestrator.py`.
Cross-boundary coordinators: they run inside the *same transaction* as the part/item create so
the index can never drift from its source.

```
PartAliasOrchestrator.on_part_created(part, actor)
   └▶ AliasFactory.for_string(part, part.part_number, INTERNAL, source=auto, actor)  # PART_TO_STRING

SupplierAliasOrchestrator.on_supplier_item_created(item, actor)
   └▶ AliasFactory.for_vendor_item(item.internal_part, item,
                                   item.manufacturer_part_number, MPN, source=auto, actor)  # PART_TO_VENDOR_ITEM
```

**Wiring decision (resolve at implementation):** connect via either (a) an explicit call from
`PartFactory.create` / `SupplierItemFactory.create` (the documented Phase 2 hook), or (b) a
Django `post_save` signal. Prefer the **explicit call** so the alias write joins the same
`transaction.atomic()` deterministically — signals make transactional boundaries fuzzier. The
Phase 2 no-op placeholder becomes this call.

---

## `AliasResolver` — value → Part (the heart of search)

`resolvers/alias_resolver.py` (or `handlers/`). Read-only; collapses both alias kinds to a Part.

```
AliasResolver.resolve(value: str) -> list[PartStruct]
  1. normalize(value)
  2. Alias.objects.filter(normalized_value=...) (exact) -> then prefix fallback (OQ7)
       .select_related('part')
  3. map each hit to its Part: alias.part   (DIRECT — primary anchor, no forward hop — D9)
  4. distinct parts -> [PartStruct.from_part(p) for p in parts]
```

Single batched query (no N+1) via `select_related('part')`. Resolution no longer follows
`supplier_item` forward — the primary `part` is stored on every alias ([D9](../decisions.md)). The
caller never branches on `association_type` — the resolver always yields Parts.

---

## `PartSearch` — presentation-layer search entry

`presentation_layer/search/part_search.py`. The seam Phase 4's lookup page calls. Thin wrapper
over `AliasResolver` plus optional direct `Part` name/number matching (OQ7).

```
PartSearch.query(term: str, *, format=...) -> list[PartStruct]
   - alias hits (AliasResolver) ∪ direct part_number/name matches
   - de-duplicated, ordered: exact alias > prefix alias > name contains (provisional, OQ7)
```

---

## Delegation summary

```
part created     ─▶ PartFactory.create(...)  ──(same txn)──▶ PartAliasOrchestrator.on_part_created
                                                               └▶ AliasFactory.for_part(INTERNAL)

item created     ─▶ SupplierItemFactory.create(...) ─(same txn)─▶ SupplierAliasOrchestrator
                                                               └▶ AliasFactory.for_supplier_item(MPN)

manual alias     ─▶ AliasFactory.for_string(NSN|LEGACY|regional, source=manual)        (PART_TO_STRING)
alt part number  ─▶ AliasFactory.for_alternate_part(part, other_part, ..., source=manual)  (PART_TO_PART)

technician search ─▶ PartSearch.query("MPN-1234")
                      └▶ AliasResolver.resolve()
                           └▶ alias.part   ⇒  PartStruct   (direct primary anchor — spec §3, D9)
```

This is the phase that makes [D3](../decisions.md) pay off: every search path, regardless of
which number was typed, terminates at a base **Part id**.
