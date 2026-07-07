# Control-Layer Diagram — Part Definitions Kit

A companion to [`model_diagram.md`](model_diagram.md): that file shows the **tables**; this one shows
the **control-layer objects** (Structs, Contexts, Factories, Managers, Handlers, Validators,
Orchestrators, Narrators, Resolvers, Search) and **how they delegate to each other**. Draft for
review — **not** part of the kit-builder required-document set. Synthesized from the three
`control_layer_plan.md` files; if they disagree, those win. Home for all of this: `app/parts/control_layer/`
(plus `presentation_layer/search/` for `PartSearch`).

Suffix meanings per [`OOP_CONTROL_PATTERNS`](../docs/ARCHITECTURE/OOP_CONTROL_PATTERNS.md).

---

## Role legend (which suffix does what here)

| Suffix | Role in this kit | Reads/Writes |
| :--- | :--- | :--- |
| `Struct` | Read-only aggregated view model; `.from_id()` / `.to_dict()`. The shape a consumer gets. | read |
| `Context` | Stateful entry point around **one** entity id; exposes reads, **delegates** all writes to managers. | read + delegate |
| `Factory` | Stateless creator (class methods); owns one entity's creation transaction. | write |
| `Manager` | The **only** writer of a particular thing; owns its allocation/mutation rules. | write |
| `Handler` | Coordinated multi-row operation (e.g. rebase a set from a template). | write |
| `Orchestrator` | Cross-boundary coordinator run **inside another entity's transaction** (the alias hooks). | write |
| `Validator` (`*_guard.py`) | Single source of truth for invariants; called by factories/managers. | check |
| `Resolver` | Read-only lookup that collapses many alias kinds to a Part. | read |
| `Narrator` | Human-readable audit strings; no writes. | format |
| `Search` (presentation) | Thin search entry the UI calls; wraps the resolver + direct matches. | read |

---

## Phase 1 — Internal Parts (the hub)

```
                         ┌─────────────────────────────────────────────┐
   read a part  ────────▶│  PartContext(part_id, actor)                │
                         │   .struct()  .current_revision()  .revisions│
                         │   .documents()  .comments()                 │
                         │   .supplier_items()   ← (added in Phase 2)   │
                         └──┬───────────────┬───────────────┬──────────┘
                            │ builds         │ delegates      │ delegates writes
                            ▼ (read)         ▼ writes         ▼
                   ┌─────────────────┐  ┌──────────────────────┐  ┌─────────────────────┐
                   │ PartStruct      │  │ PartRevisionManager  │  │ PartThreadManager   │
                   │ PartRevisionStr.│  │  .release_major()    │  │  .attach_document() │
                   └─────────────────┘  │  .redline()          │  │  .add_comment()     │
                                        │  .set_status()       │  │  (shared helper)    │
                                        └─────────┬────────────┘  └──────────┬──────────┘
                                                  │ narrates                 │ fronts
                                                  ▼                          ▼
                                        ┌──────────────────────┐   events.ActivityThread
                                        │ PartRevisionNarrator │   + Comment / Attachment
                                        └──────────────────────┘   + FileHandler (D5)

   create a part ──▶ PartFactory.create(input, actor)        [one transaction.atomic()]
                       ├▶ PartValidator.check()              (part_number present + unique)
                       ├▶ Part.objects.create()              (the hub)
                       ├▶ PartRevisionManager.release_major(major=1, minor=0, DRAFT)  (base rev)
                       └▶ << alias hook >>                   (no-op; Phase 3 → PartAliasOrchestrator)

   domain scope ──▶ PartDomainManager(part, actor)          (only writer of mapping rows + flag)
   (D14)              .set_limited()  .add_domain()  .remove_domain()  .domains()
                    PartDomainTemplateHandler(part, actor)
                      .apply(template_id)  ──reads──▶ administration.DomainTemplate / DomainTemplateItem
                                           ──writes─▶ PartDomainAccessMapping rows (rebase on re-issue)
```

**Writers in Phase 1:** `PartFactory` (the Part + its base revision), `PartRevisionManager` (all
revisions), `PartThreadManager` (comments/docs), `PartDomainManager` + `PartDomainTemplateHandler`
(domain scope). `PartContext` writes **nothing** itself — it only delegates.

---

## Phase 2 — Supplier Mapping (satellites)

```
   register mfr ──▶ PartManufacturerFactory.create(data, actor)
                      └▶ PartManufacturerValidator.check()   (name/code uniqueness)

                    PartManufacturerContext(id, actor) .struct() .supplier_items()
                      └ builds PartManufacturerStruct

   map an item ──▶ SupplierItemFactory.create(input, actor)   [one transaction.atomic()]
                      ├▶ SupplierItemValidator.check()        (mfr + internal Part exist, MPN,
                      │                                         (mfr,mpn) unique; compat range as-is)
                      ├▶ SupplierItem.objects.create(mfr, part, compat range)   (forward map — D6/D7/D13)
                      ├▶ (NO base revision — D13)
                      └▶ << alias hook >>                     (no-op; Phase 3 → SupplierAliasOrchestrator)

   read an item ─▶ SupplierItemContext(item_id, actor)
                      .struct()                ── builds ──▶ SupplierItemStruct (resolves fwd to Part)
                      .compatibility_range()  .satisfies(major, minor)        (null-aware range — D13)
                      .vendor_revisions()  .documents()  .comments()
                      .thread  ───────────────────────────▶ PartThreadManager   (SHARED w/ Phase 1)
                      │
   log vendor rev ─▶ SupplierVendorRevisionManager(item_id, actor)
                      .record(vendor_revision_id, note)  ─▶ one append-only JSON Comment on the
                      .list()                                item thread (NO revision row — D13)
                                                            └▶ narrates ▶ SupplierItemNarrator

   part → options ─▶ PartContext.supplier_items()           (read-only forward; Part stays independent — D3)
```

**Reuse:** supplier items lean on the **same `PartThreadManager`** from Phase 1 for comments/docs —
no parts-local file plumbing. No `SupplierItem*Revision` manager exists (D13).

---

## Phase 3 — Aliases & Unified Search (the payoff)

```
   AliasFactory  (the ONLY alias writer; sets association_type + matching secondary FK — D9)
      .for_string(part, alias, alias_type, source, actor)               → PART_TO_STRING
      .for_vendor_item(part, item, alias, alias_type, source, actor)    → PART_TO_VENDOR_ITEM
      .for_alternate_part(part, other_part, alias, alias_type, …)       → PART_TO_PART
         └▶ AliasValidator  (non-empty; (alias_type, normalized_value) uniqueness)

   ── auto-population orchestrators (run INSIDE the Phase 1/2 create transactions) ──
   PartAliasOrchestrator.on_part_created(part, actor)
        └▶ AliasFactory.for_string(part, part_number, INTERNAL, auto)        ◀── wired into PartFactory
   SupplierAliasOrchestrator.on_supplier_item_created(item, actor)
        └▶ AliasFactory.for_vendor_item(item.internal_part, item, MPN, auto) ◀── wired into SupplierItemFactory

   ── the search path ──
   PartSearch.query(term)                 (presentation_layer/search/ — what the Phase 4 UI calls)
      ├▶ AliasResolver.resolve(value)
      │     normalize → Alias.filter(normalized_value=…) .select_related('part')
      │     → alias.part  DIRECTLY  (primary anchor, no forward hop — D9)
      │     → [PartStruct.from_part(p) …]      (reuses Phase 1 PartStruct)
      └▶ ∪ direct part_number/name matches → de-dup, ranked (OQ7)
```

**Cross-phase wiring:** the two **Orchestrators** are the glue — the `<< alias hook >>` no-ops left in
`PartFactory` (Phase 1) and `SupplierItemFactory` (Phase 2) become explicit calls here, joining the
**same** `transaction.atomic()` so the index can never drift from its source.

---

## Cross-cutting collaborations (who depends on whom)

```
 PartContext ──delegates──▶ PartRevisionManager ──narrates──▶ PartRevisionNarrator
     │                          │
     │                          └──guarded by──▶ PartValidator (shared w/ PartFactory)
     ├──delegates──▶ PartThreadManager ◀──reused by── SupplierItemContext / SupplierVendorRevisionManager
     ├──delegates──▶ PartDomainManager,  PartDomainTemplateHandler ──▶ administration.Domain*/Template
     └──reads──────▶ PartStruct ◀──reused by── AliasResolver (resolve() returns PartStructs)

 PartFactory ──(same txn)──▶ PartAliasOrchestrator ──▶ AliasFactory ◀── SupplierAliasOrchestrator ◀──(same txn)── SupplierItemFactory

 PartSearch ──▶ AliasResolver ──▶ Alias.part ──▶ PartStruct        (every typed number ends at a base Part id — D3)
```

**Shared seams worth noting for review:**
- **`PartThreadManager`** is the one comments/documents helper for *every* threaded entity (Part,
  PartRevision, SupplierItem) — a single place for all parts↔`events` plumbing (D5).
- **`PartStruct`** is produced by Phase 1 but consumed by Phase 3's resolver/search — the read model
  is shared, not duplicated.
- **`PartValidator`** is the single invariant source for both `PartFactory` and any future import/seed.
- The **Orchestrators** are the only objects that cross entity boundaries; everything else stays
  within its own entity's transaction.

---

## Open points for your review

1. **Resolver home** — `AliasResolver` is sketched under `resolvers/` or `handlers/`; pick one
   (suffix vocabulary has no `Resolver` — is it a `Handler`?).
2. **Domain enforcement seam** — `PartDomainManager` writes scope, but the read-side filter (which
   Parts a user may see) is deferred to a later RBAC pass (D11/D14). Where should that filter attach —
   `PartContext`, `PartSearch`, or a dedicated policy/guard?
3. **Alias hook mechanism** — explicit factory call vs. `post_save` signal (the plans recommend the
   explicit call for transactional determinism). Confirm.
4. **`PartManufacturerContext`** is thin — is a Context warranted, or fold its two reads into a Struct?
