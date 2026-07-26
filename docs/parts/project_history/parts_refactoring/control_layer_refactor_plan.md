# Control layer refactor investigation — `app/parts`

Planning only. Triggered by the observation that a large share of
`app/parts/control_layer/` files are under 50 lines. Line counts, then a finding-by-finding read of
every file under 50 lines to separate **intentionally small** (leave alone) from **duplicated /
broken** (worth fixing).

## 1. Line count survey

```
 12  adapters/manufacturer_create_adaptor.py
 16  narrators/supplier_item_narrator.py
 21  adapters/part_create_adaptor.py
 22  domain_structs/alias_struct.py            (dead — see struct_migration_plan.md)
 22  guards/part_validator_guard.py
 24  guards/alias_validator_guard.py
 26  orchestrators/part_alias_orchestrator.py
 28  narrators/part_revision_narrator.py
 29  orchestrators/supplier_alias_orchestrator.py
 31  guards/part_manufacturer_uniqueness_guard.py
 34  adapters/revision_append_adaptor.py
 36  adapters/supplier_item_create_adaptor.py
 37  domain_structs/part_manufacturer_struct.py (dead — see struct_migration_plan.md)
 40  factories/part_manufacturer_factory.py
 45  domain_structs/part_revision_struct.py
 45  guards/supplier_item_validator_guard.py
 47  managers/supplier_vendor_revision_manager.py
 49  domain_structs/supplier_item_struct.py
```
18 of 26 files (69%) are under 50 lines. **Being small is not itself a problem** —
`oop_control_patterns.md` explicitly prefers "many small files over few large ones." The question is
whether the *content* of these small files is duplicated or broken, not whether they should be merged
for size's sake.

## 2. Verdict by category

### Guards — correctly sized, leave alone
`part_validator_guard.py`, `alias_validator_guard.py`, `part_manufacturer_uniqueness_guard.py`,
`supplier_item_validator_guard.py` are one Validator per aggregate, each with a distinct uniqueness
rule against a distinct model. Merging them into one `PartsValidator` would violate the
"decomposition over consolidation" principle and make each one harder to find by filename. **No
action.**

### Orchestrators — correctly sized, leave alone
`part_alias_orchestrator.py` / `supplier_alias_orchestrator.py` are deliberately thin (D8: "One write
path owns alias creation so the index never drifts") — each is a named hook seam for a specific
create event, not a place to add logic. Collapsing them into one `AliasOrchestrator` with two methods
would work mechanically, but the current split matches "Phase 1 create hook" / "Phase 2 create hook"
language directly from the decisions doc, which is worth keeping legible when Phase 3+ hooks get
added. **No action** — low-value merge, would reduce traceability to the decision doc.

### Adapters — real duplication, worth fixing
Every adapter re-implements two tiny helpers by hand:
- **Checkbox truthiness** — `post.get(key) in ("on", "true", "True", "1")` appears **3 times**
  verbatim: `manufacturer_create_adaptor.py`, `part_create_adaptor.py` (as `_checkbox`),
  `supplier_item_create_adaptor.py`.
- **Int-or-None parsing** — `_to_int` appears **twice** verbatim: `revision_append_adaptor.py`,
  `supplier_item_create_adaptor.py`.

**Recommendation:** extract one shared module, e.g. `control_layer/adapters/form_parsing.py`, with
`parse_checkbox(post, key)` and `parse_int(value)`. Each `*CreateAdaptor` class stays separate (one
per write target, matching the Adaptor pattern) — only the free-function helpers consolidate. This is
a pure dedup, not a class merge: ~4 call sites shrink by one local function each, zero behavior
change.

### Narrators — duplication is not the finding; **dead return values are**
Both narrators are fine in isolation, but tracing their call sites:

```python
# managers/part_revision_manager.py:49
PartRevisionNarrator.major_released(self.part, revision)   # return value discarded
```
```python
# factories/supplier_item_factory.py:54
SupplierItemNarrator.item_mapped(item, part)                # return value discarded
```

Every narrator call in the app builds a human-readable string and then **throws it away** — nothing
logs it, stores it as a comment, or surfaces it to the UI. This isn't a size problem; it's a narrator
pattern that was wired in per the playbook (`oop_control_patterns.md` step 5: "Narrator — audit and
user-visible strings where needed") but never connected to a sink. Two real options, not a size fix:
1. Wire the return value into `PartThreadManager.add_comment(...)` as a system comment (`is_human_made=False`) on the relevant thread — gives revisions/supplier items an audit trail for free, matching how `events.Comment.is_human_made` already exists to distinguish system-authored entries.
2. Or remove the narrator calls if audit text isn't actually wanted yet, and reintroduce them when a sink exists — calling a class purely for its side-effect-free string and discarding it is dead work on every write.

**Recommendation: option 1.** The `is_human_made` flag already exists on `Comment` for exactly this
purpose (see `EventDetailStruct`'s `include_shadow_comments` handling of non-human comments) — wiring
narrators into it costs one line per call site and finally gives revisions and supplier items the
audit trail the Narrator suffix implies they should have.

### Factories/Managers — real duplication: `*ValidationError` defined 4 times in this app alone
Identical shape, defined independently in four files:

```python
class XValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))
```

Found in `factories/part_factory.py` (`PartValidationError`), `factories/part_manufacturer_factory.py`
(`PartManufacturerValidationError`), `factories/supplier_item_factory.py`
(`SupplierItemValidationError`), `factories/alias_factory.py` (`AliasValidationError`) — **and**
`managers/part_manager.py` redefines `PartValidationError` **again**, byte-for-byte identical to the
one in `part_factory.py`. That duplicate is why `presentation_layer/entrypoints/parts.py` has to import
one under an alias to avoid a name collision:

```python
from app.parts.control_layer.factories.part_factory import PartValidationError
from app.parts.control_layer.managers.part_manager import (
    PartValidationError as PartEditValidationError,
)
```

That import alias is a symptom, not a style choice — it exists purely because the same class was
declared twice. **Recommendation:** delete the copy in `part_manager.py`, have it import
`PartValidationError` from `part_factory.py` (or lift both to a shared
`control_layer/errors.py::PartValidationError` if `factories/` importing from `managers/` — or vice
versa — is considered an awkward direction). Either way, `part_edit`'s alias import disappears along
with the duplicate class.

**Wider pattern (informational, out of scope for this app):** the same
`class XValidationError(Exception): __init__(errors) -> "; ".join`) shape recurs **11 more times**
across `app/assets/control_layer/` (`AssetValidationError`, `AssetClassValidationError`,
`ManufacturerValidationError`, `AssetModelValidationError`, `CapabilityDefinitionValidationError`,
each declared twice — once in a `*_context.py` and once in the matching `factories/*.py`, same
collision shape as `Part`/`PartManager` here). That's a project-wide candidate for a single shared
`ValidationError` base in something like `app/utils/control_layer_errors.py`, but it's a cross-app
decision outside this parts-only investigation — flagging it here since the parts-app fix is the same
shape, not proposing to touch `assets/` as part of this plan.

### Domain structs under 50 lines
`part_revision_struct.py` (45) and `supplier_item_struct.py` (49) are correctly-sized base/identity
structs per `harness/Architecture/patterns/domain_structs_cont.md` §1 — one row + `select_related` FKs,
existence guarantee, `to_dict()`. **No action** beyond what's already covered in
`struct_migration_plan.md` (the *dead* structs, not these two).

## 3. Summary of actionable items (parts app only)

| # | Finding | Fix | Size |
| :--- | :--- | :--- | :--- |
| 1 | Checkbox/int parsing duplicated across 3-4 adapters | Extract `adapters/form_parsing.py` shared helpers | small |
| 2 | Narrator return values always discarded — no audit trail is actually produced | Wire narrator strings into `PartThreadManager.add_comment(..., is_human_made=False)` at the 2 call sites | small |
| 3 | `PartValidationError` defined twice in this app, forcing an import alias in `parts.py` | Delete the `part_manager.py` copy; import the one from `part_factory.py` | trivial |
| 4 | (informational) Same `*ValidationError` duplication pattern recurs 11x in `assets/` | Cross-app decision, not part of this plan | — |

None of these are "merge small classes into bigger ones" — the guards, orchestrators, and small
structs are correctly scoped per the architecture's own decomposition preference. The real yield here
is deduplicating hand-rolled helpers and fixing one accidental double-declaration, not shrinking file
count.
