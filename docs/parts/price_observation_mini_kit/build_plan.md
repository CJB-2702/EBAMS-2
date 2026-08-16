---
okf_version: "0.1"
type: "Procedure"
title: "Build Plan — Part Price Observations"
description: "Executable, phase-by-phase build instructions for the price observation kit: kit-drift corrections the builder must apply, exact file paths and signatures, verification steps, and explicit non-goals."
tags: [procedure, procurement, pricing, build-plan, backend]
context_tier: 2
personas: [backend, frontend]
---

# Build Plan — Part Price Observations

**Audience:** an implementing agent with no prior context on this kit.
**Read before starting, in this order:** [README.md](README.md) (decisions D79–D92),
[models/part_price_observation.md](models/part_price_observation.md),
[control_layer_architecture.md](control_layer_architecture.md),
[parts_creation_smuggling.md](parts_creation_smuggling.md),
[bulk_observation_screen.md](bulk_observation_screen.md),
[purchase_order_integration.md](purchase_order_integration.md), [page_set.md](page_set.md).
Then `.claude/CLAUDE.md` and `harness/Architecture/layer_rules.md`.

**§1 below overrides all of them where they disagree.** The kit was revised mid-design (D87–D92 came
after D79–D86) and three documents still carry superseded text. Do not resolve those conflicts by
judgement — apply §1 literally.

---

## §1 — Kit-drift corrections (authoritative)

| # | Stale text | Where | What to build instead |
| :--- | :--- | :--- | :--- |
| 1.1 | "global observations", `domain_id: int \| None`, `_visible_domain_ids` returning `None`, `domain_name = "Global"`, "blank means a global observation" | `control_layer_architecture.md` §PartPricePolicy + §struct; `bulk_observation_screen.md` §Layout | **D87: `domain` is `NOT NULL`.** No `None` anywhere in a visible-domain set. No "Global" label. A blank domain on the grid is a **validation error**, not a global row. |
| 1.2 | The three-rung ladder; `rung: int`; `is_exact_vendor_match`; `autofills: bool`; `PartPricePolicy.suggest()` returning one ranked answer | `control_layer_architecture.md`; `purchase_order_integration.md` §1 rung table | **D91: two facts, no ranking.** The policy returns *most recent recorded* and *most recent verified*, both restricted to the **PO's vendor** and the actor's visible domains. Cross-vendor prices are reachable only through the picker (D92), never through the chip's `Use this`. |
| 1.3 | `FIRM` / `ESTIMATED` `pricing_basis` header field on `PurchaseOrder` | `purchase_order_integration.md` §3 | **D88 replaced it.** Do **not** add the column. Basis is derived from the lines' `confidence` values. |
| 1.4 | Observation columns without `confidence` / `is_verified` | `control_layer_architecture.md` call graph | Both columns exist (D88, D89). `confidence` is **required with no default** on every write path; `is_verified` is write-at-insert only and never updated. |
| 1.5 | "`_visible_domain_ids(actor)` reads `administration.UserDomain`" | `control_layer_architecture.md`, `parts_creation_smuggling.md` | The project already has this: `app/procurement/presentation_layer/tools/procurement_access.py::accessible_domain_ids(request)` (login-snapshot, [D5]). **The entrypoint reads it and passes `domain_ids: list[int]` down.** The control layer never touches `request` or the session. |
| 1.6 | "Part not in the actor's visible domains" as if `Part` had a domain FK | `bulk_observation_screen.md`, `page_set.md` | `Part` has **no domain FK**. Visibility is `Part.is_domain_limited=False` **OR** an active `PartDomainAccessMapping` to a visible domain. See §2.4 for the one canonical predicate — write it once, call it everywhere. |
| 1.7 | "Reuse `procurement.buy` for the first cut" | `control_layer_architecture.md` §Permissions | Recording still gates on `procurement.buy`. **Verifying needs its own permission** — D89's establish level is per-domain and cannot be expressed by `buy`. Add `price_establish` (§3.1). D90's soft lock on the *Use* level is **deferred** (§7). |

If you find a conflict §1 does not cover, stop and report it rather than picking a side.

---

## §2 — Ground rules for every phase

1. **One schema pass.** All schema in this kit — the new table *and* the three `PurchaseOrderLine`
   columns — lands in **Phase 1**, even though the columns have no UI until Phase 5. Two schema
   passes means two full database resets.
2. **Full reset, never an incremental migration.** After Phase 1's model work:
   `python refresh_project.py`. Delete nothing by hand.
3. **Layer rules.** Entrypoints never touch `PartPriceObservation.objects`. Writes go
   adaptor → factory → guard. Reads >2 tables go in `presentation_layer/search/` or a policy.
4. **One visibility predicate.** Write `visible_part_ids(...)` / `visible_parts_qs(...)` once (§2.4)
   and import it. A second copy is how one branch loses its filter.
5. **Every card renders when empty.** Grid with zero rows, unpriced queue with zero rows, history
   with zero observations — header plus explicit empty state, never `{% if %}` around the card.
6. **F5 rule.** Every state reachable by HTMX must render identically on a plain GET.
7. **Domain filtering is a security boundary.** Apply it *before* ordering, on every read path,
   including the breadcrumb re-read.
8. Follow existing house style: `from __future__ import annotations`, keyword-only signatures,
   module docstring naming the decision numbers the file implements.

### 2.4 — The visibility predicate

```python
# app/procurement/presentation_layer/search/part_visibility.py
def visible_parts_qs(*, domain_ids: list[int]) -> QuerySet[Part]:
    """Parts this actor may see. D14: a part is global unless is_domain_limited,
    in which case it needs an active mapping into one of the actor's domains."""
    return Part.objects.filter(
        Q(is_domain_limited=False)
        | Q(
            domain_access_mappings__domain_id__in=domain_ids,
            domain_access_mappings__is_active=True,
        )
    ).distinct()
```

An empty `domain_ids` list still returns global parts. That is correct and matches
`accessible_domain_ids`' documented reading.

---

## §3 — Phase 1: schema

### 3.1 Files

```
app/procurement/models/pricing/__init__.py                 NEW
app/procurement/models/pricing/enums.py                    NEW
app/procurement/models/pricing/part_price_observation.py   NEW
app/procurement/models/__init__.py                         EDIT — re-export + __all__
app/procurement/models/purchasing/purchase_order_line.py   EDIT — three columns
app/procurement/presentation_layer/tools/procurement_access.py  EDIT — PERM_PRICE_ESTABLISH
app/administration/fixtures/dev_auth_groups.json           EDIT — grant the new perms in dev
```

### 3.2 `models/pricing/enums.py`

```python
class PriceSourceType(models.TextChoices):
    PART_CREATE = "part_create", "Part creation"
    QUOTE = "quote", "Quote"
    MANUAL = "manual", "Manual"
    ORDERED = "ordered", "Ordered"
    INVOICED = "invoiced", "Invoiced"
    CATALOG = "catalog", "Catalog"      # reserved; nothing writes it


class PriceConfidence(models.TextChoices):   # D88 — no default; the asserter chooses
    QUOTED = "quoted", "Quoted — I have paper"
    P10 = "p10", "Within ~10%"
    P50 = "p50", "Within ~50%"
    P100 = "p100", "Could be double"
    UNKNOWN = "unknown", "No idea"


class UnitCostSource(models.TextChoices):    # D85 — PurchaseOrderLine
    QUOTED = "quoted", "Quoted"
    LAST_PAID = "last_paid", "Last paid"
    LAST_ORDERED = "last_ordered", "Last ordered"
    ESTIMATED = "estimated", "Estimated"
    UNKNOWN = "unknown", "Unknown"

UNIT_COST_SOURCE_UNSET = ""   # follows APPROVAL_STATE_UNSET's precedent
```

Values are lowercase snake to match `PurchaseOrderStatus` / `DemandState` in this app. The kit's
prose writes them uppercase; that is prose, not the stored value.

### 3.3 `PartPriceObservation`

Exactly as [models/part_price_observation.md](models/part_price_observation.md) specifies —
columns, `Meta`, four indexes, two check constraints, `db_table = "part_price_observation"`.
Confirmations that matter:

- `AuditFieldsMixin` only. **No `SoftDeleteMixin`** — append-only (D80).
- `domain`: `PROTECT`, **not nullable** (D87, §1.1).
- `confidence`: `CharField(10)`, `choices=PriceConfidence.choices`, **no `default=`**.
- `is_verified`: `BooleanField(default=False)`, docstring stating it is written at insert and never
  updated (D89).
- No unique constraint. No `@property`. No business logic (D53).
- Add `Meta.permissions = [("price_establish", "Can verify a price observation, making it the "
  "established price for its domain")]`.

### 3.4 `PurchaseOrderLine` — three new columns

| Column | Definition |
| :--- | :--- |
| `unit_cost_source` | `CharField(max_length=20, choices=UnitCostSource.choices, blank=True, default="")` |
| `unit_cost_asserted_at` | `DateField(null=True, blank=True)` — the observation's `observed_at`, never `today` |
| `unit_cost_confidence` | `CharField(max_length=10, choices=PriceConfidence.choices, blank=True, default="")` — D88, the buyer's own band for *this* line |

`unit_cost_confidence` is the piece D88 added that the model doc's PO-line table predates. It is
blank-by-default on the line (unlike the observation, which requires it) because pre-existing rows
have no answer and the derived-basis rendering in Phase 6 treats blank as "not stated".

### 3.5 Permissions

In `procurement_access.py`, alongside the existing constants:

```python
#: D89 establish level — verify a price so it becomes what everyone else is shown.
#: Recording an (unverified) observation needs only PERM_BUY.
PERM_PRICE_ESTABLISH = "procurement.price_establish"

def can_establish_price(request) -> bool: ...
def require_buy_prices(request) -> None: ...   # thin alias over require_buy, named for the caller
```

Declaring the codename on `PartPriceObservation.Meta.permissions` (§3.3) matches how this app already
does it — `buy` / `purchase_approve` sit on `PurchaseOrder.Meta`, `request` / `demand_manage` on
`PartDemand.Meta`. Nothing new is invented here.

**The permission must also be granted in dev,** or the establish path is unreachable and the §9
checklist can only be tested in the negative. In `dev_auth_groups.json`, the `procurement_super_user`
group lists custom codenames alongside the model CRUD ones (`["buy", "procurement", "purchaseorder"]`
at line 94). Add, in the same group:

```json
["add_partpriceobservation", "procurement", "partpriceobservation"],
["view_partpriceobservation", "procurement", "partpriceobservation"],
["price_establish", "procurement", "partpriceobservation"]
```

No `change_` / `delete_` — the table is append-only (D80), and granting them in the seed invites a
future screen that uses them. Keep a `buy`-only dev user without `price_establish`; the §9 checklist
needs both sides of that fence to be walkable.

**Per-domain establish authority (D89) is not enforced in Phase 1.** Django permissions are global;
scoping them per domain is an admin-engineering task. Phase 1 ships the global permission plus a
`# TODO(D89)` at the single call site in the guard where the domain check belongs. Note it in
`docs/procurement/tech_debt/`.

### 3.6 Verification

```bash
python refresh_project.py
python manage.py check
```
Then a shell smoke: create an observation, assert the check constraints reject `unit_cost=-1` and
`quantity=0`.

---

## §4 — Phase 2: control layer (writes)

```
app/procurement/control_layer/guards/part_price_observation_guard.py     NEW
app/procurement/control_layer/factories/part_price_observation_factory.py       NEW
app/procurement/control_layer/factories/part_price_observation_bulk_factory.py  NEW
app/procurement/control_layer/adapters/part_price_grid_adaptor.py        NEW
app/procurement/control_layer/narrators/part_price_narrator.py           NEW
```

### 4.1 `PartPriceObservationValidator` (in `..._guard.py`)

Raises `ProcurementValidationError(errors: list[str])` from
`app/procurement/control_layer/errors.py` — do **not** declare a new exception class.

```python
@dataclass(frozen=True)
class DuplicateObservationWarning:
    part_id: int
    existing_observation_id: int
    message: str


class PartPriceObservationValidator:
    @classmethod
    def validate(
        cls,
        *,
        part_id: int,
        vendor_id: int,
        domain_id: int,
        unit_cost: Decimal,
        quantity: Decimal | None,
        observed_at: date,
        confidence: str,
        is_verified: bool,
        visible_part_ids: set[int],
        visible_domain_ids: list[int],
        actor_can_establish: bool,
    ) -> list[DuplicateObservationWarning]:
        """Hard errors raise; duplicates come back as warnings (D80: no unique
        constraint — two people entering the same quote is legitimate)."""
```

Hard rules: `unit_cost >= 0`; `quantity is None or quantity > 0`; `observed_at <= today`; vendor
exists and is active; `domain_id` present **and in `visible_domain_ids`**; `part_id` in
`visible_part_ids`; `confidence` in `PriceConfidence.values`; `is_verified=True` only when
`actor_can_establish` (`# TODO(D89)`: narrow to the row's domain once per-domain authority exists).

Warning rule: an existing row with identical `(part, vendor, domain, observed_at, unit_cost)`.

### 4.2 Factory / BulkFactory

```python
class PartPriceObservationFactory:
    @classmethod
    def create(cls, *, part_id, vendor_id, domain_id, unit_cost, quantity=None,
               currency="USD", observed_at, source_type, confidence,
               is_verified=False, source_po_line_id=None, notes="",
               actor=None, commit=True) -> PartPriceObservation: ...


class PartPriceObservationBulkFactory:
    @classmethod
    def create_many(cls, *, rows: list[PriceObservationInput], actor,
                    visible_part_ids: set[int], visible_domain_ids: list[int],
                    actor_can_establish: bool,
                    ) -> BulkObservationResult: ...
```

- `create_many` validates **every** row first, collects all errors, and raises once — never
  half-validates then half-writes.
- Wrap in a single `transaction.atomic()` and use `bulk_create`. All-or-nothing.
- `BulkObservationResult` is a frozen dataclass: `created_ids`, `warnings`, `dropped_part_ids`
  (rows the adaptor dropped for having no cost — carried through so the page can list them by part
  number rather than silently losing them).
- The guard call belongs in the factory, not the entrypoint.

### 4.3 `PartPriceGridAdaptor`

Mirrors [`PartCreationWizardAdaptor`](../app/parts/control_layer/adapters/part_creation_wizard_adaptor.py):
indexed `rows-<i>-part_id`, `rows-<i>-quantity`, `rows-<i>-unit_cost`; batch header fields
`vendor_id`, `domain_id`, `observed_at`, `source_type`, `confidence`, `notes` applied to every
surviving row.

- **A row with no `unit_cost` is dropped** — mirrors the `if not mpn: continue` pattern — but its
  `part_id` goes into `dropped_part_ids`.
- Normalize money on the way in: strip `$`, spaces, and thousands separators before `Decimal(...)`;
  an unparseable value is an error, not a silent zero.
- Also owns `to_session(draft) -> dict` / `from_session(raw) -> list[PriceObservationInput]`, the
  same handoff `PurchaseOrderDraftAdaptor` has with `po_wizard_draft`.

### 4.4 `PartPriceNarrator`

Static methods over a struct or an observation row. One place for every price phrase:
`describe_recorded()`, `describe_verified()`, `describe_absent(vendor_name)`, `staleness(observed_at)`.
Follow [`purchase_order_narrator.py`](../app/procurement/control_layer/narrators/purchase_order_narrator.py).
No template does its own date maths — that is the whole reason this file exists.

### 4.5 Tests (`app/procurement/tests/test_price_observations.py`)

- Guard: each hard rule rejects; a duplicate warns but does not raise.
- Guard: `is_verified=True` without `price_establish` raises. **Write this one first.**
- Bulk atomicity: one bad row in ten writes zero rows.
- Adaptor: costless rows dropped and reported; `"$1,234.56"` parses to `Decimal("1234.56")`.

---

## §5 — Phase 3: session tools and the parts breadcrumb

```
app/procurement/presentation_layer/tools/recent_part_creations.py   NEW
app/procurement/presentation_layer/tools/price_grid_draft.py        NEW
app/parts/presentation_layer/entrypoints/parts.py                   EDIT — one call
app/parts/presentation_layer/entrypoints/parts_bulk_upload.py       EDIT — one call
```

Build [parts_creation_smuggling.md](parts_creation_smuggling.md) exactly. The non-negotiables:

1. The `# DELIBERATE ANTI-PATTERN (D81)` block at the top of `recent_part_creations.py`, verbatim
   from that document.
2. **Three public functions only** — `record_created_parts`, `read_recent`, `consume`.
   `SESSION_KEY` is module-private and nothing outside this file may name it.
3. **Read, mutate locally, reassign the whole key.** Never mutate the nested dict in place
   (hazard 1 — it appears to work and loses data on the *next* request).
4. **Append, never replace** (D82). Dedupe by `part_id` keeping the earliest `created_at`. Cap at
   `MAX_PARTS = 100`, setting `overflowed = True`. `TTL` is a module constant filtered on read —
   pick a placeholder (`timedelta(hours=12)`) and comment that the value is owned by the later
   app-hardening pass.
5. `read_recent(request, *, actor)` prunes expired entries, re-runs `visible_parts_qs` (§2.4),
   drops missing parts, and returns survivors **silently** — never "3 parts were hidden".
6. Both call sites use `transaction.on_commit(...)`, sit **after** the factory returns, and carry a
   one-line `# DELIBERATE ANTI-PATTERN (D81)` comment. `PartCreationWizardFactory` and
   `PartBulkUploadFactory` stay untouched.
7. `domain_ids_by_part` comes from the part's active `PartDomainAccessMapping` rows at creation
   time — a fact about the creation event, deliberately denormalized.

`price_grid_draft.py` follows [`po_wizard_draft.py`](../app/procurement/presentation_layer/tools/po_wizard_draft.py):
`empty_draft()`, `load(session)`, `save(session, draft)`, `clear(session)`, plus `add_rows`,
`remove_row`, `set_header`. **A separate session key from the breadcrumb** — conflating them lets a
half-typed grid resurrect already-priced parts.

**Test that matters:** breadcrumb persistence across a real request boundary using the Django test
client, not an in-memory dict assertion. An in-memory test passes against the nested-mutation bug,
which makes it worse than no test. Also: a rolled-back part creation leaves no breadcrumb.

---

## §6 — Phase 4: reads, routes, pages

```
app/procurement/presentation_layer/search/part_visibility.py       NEW (§2.4)
app/procurement/presentation_layer/search/unpriced_part_search.py  NEW
app/procurement/presentation_layer/search/part_price_history_search.py NEW
app/procurement/presentation_layer/entrypoints/prices.py           NEW
app/procurement/urls_prices.py                                     NEW
app/procurement/urls.py                                            EDIT — include
app/procurement/templates/procurement/prices/*.html                NEW
app/procurement/templates/procurement/hub.html                     EDIT — entry card
app/procurement/presentation_layer/entrypoints/shell.py            EDIT — unpriced count
```

`urls.py` follows the wave pattern already there: `path("prices/", include("app.procurement.urls_prices"))`
beside the demands / purchase-orders / packages includes. Do not hang the four routes off `urls.py`
directly the way `vendor_index` / `vendor_create` are — those two predate the convention.

### 6.0 Navigation — the routes must be reachable

A page nothing links to is not shipped. `hub.html` carries a `body-grid` of entry cards; add one
matching the existing shape (icon span, `title is-6`, grey `is-size-7` subtitle, `button is-small
is-link mt-2`) pointing at `price_hub`, and render it **only for `can_buy`** — the hub already
decides visibility per card, and a card leading to a guaranteed 403 is worse than no card.

`procurement_hub` in `shell.py` already assembles the `stat-tile` counts; add the unpriced count
from `UnpricedPartSearch` (§6.2) alongside `open_demands`. It is viewer-relative per D87 — the same
one-line caveat the unpriced page carries belongs in the tile's label, not only on the page it links
to. Reuse the search's count query; do not hand-roll a second `~Exists(...)` here (§2 rule 4 applies
to counting as much as to listing).

### 6.1 Routes

| Route | Name | Method | Notes |
| :--- | :--- | :--- | :--- |
| `/procurement/prices/` | `price_hub` | GET | Unpriced count, last ~10 observations, actions |
| `/procurement/prices/bulk/` | `price_bulk_grid` | GET, POST | The paste grid |
| `/procurement/prices/unpriced/` | `unpriced_parts` | GET | D86 backstop — **ships now, not later** |
| `/procurement/prices/parts/<int:part_id>/` | `part_price_history` | GET | D91 promoted this to first-cut |

Fragments use `?format=htmx-*` on those same URLs — never a parallel URL, never `format=` density
and `htmx-*` in the same request. `format=htmx-picker` on the history URL is D92's modal picker.

Every entrypoint: `require_buy(request)` first, then `domain_ids = accessible_domain_ids(request)`
passed downward. The recent-creations banner must not render for a user without `buy`.

### 6.2 `UnpricedPartSearch`

Parts from `visible_parts_qs(domain_ids=...)` with **zero** observations *visible to this actor*
(`~Exists(PartPriceObservation.objects.filter(part=OuterRef("pk"), domain_id__in=domain_ids))`).
Per D87 this is viewer-relative and that is intended — someone will ask; the template should say so
in one line of helper text. Filters: domain, created-since, part type. Default sort: oldest first.
Paginate.

### 6.3 The grid page

[bulk_observation_screen.md](bulk_observation_screen.md) is the spec. Corrections from §1: the
domain field is **required** (no "blank means global" hint), and the header bar carries a
**confidence** select (D88) plus, for `price_establish` holders only, a *Record as verified*
checkbox (D89).

Paste handling is ~15 lines of vanilla JS: intercept `paste`, split on `\n` then `\t`, fill down
and across from the focused cell, stop at the grid edge, report `"14 values pasted, 3 ignored —
grid has 11 rows."` Never create rows implicitly.

On success: `consume(request, part_ids=...)`, then re-render with the summary and the list of
dropped (costless) rows by part number.

### 6.4 Templates

`bulk.html`, `_grid.html`, `_recent_banner.html`, `_vendor_picker.html`, `unpriced.html`,
`part_history.html`, `hub.html` under `app/procurement/templates/procurement/prices/`, extending
`procurement/base.html`. `_vendor_picker.html` mirrors
[`parts/manufacturers/_manufacturer_picker.html`](../app/parts/templates/parts/manufacturers/_manufacturer_picker.html).
Hand the template work to `/frontend-persona`; the entrypoints and context shapes above are the
contract between them.

---

## §7 — Phase 5: the chip (D91) and the picker (D92)

```
app/procurement/control_layer/domain_structs/part_price_facts_struct.py  NEW
app/procurement/control_layer/policies/__init__.py                       NEW package
app/procurement/control_layer/policies/part_price_policy.py              NEW
```

### 7.1 The struct — two facts, no ranking

```python
@dataclass(frozen=True)
class PriceFact:
    observation_id: int
    unit_cost: Decimal
    quantity: Decimal | None
    observed_at: date
    source_type: str
    confidence: str
    is_verified: bool
    vendor_id: int
    vendor_name: str
    domain_id: int
    domain_name: str
    recorded_by_name: str


@dataclass(frozen=True)
class PartPriceFactsStruct:
    part_id: int
    vendor_id: int                 # the PO's vendor — both facts are scoped to it
    most_recent: PriceFact | None
    most_recent_verified: PriceFact | None
    other_vendor_count: int        # feeds the doorway when both are None
    def collapses(self) -> bool:   # D91 — same row, show one line
        ...
    def to_dict(self) -> dict: ...
```

No `rung`. No `autofills`. No `is_exact_vendor_match`. Both facts are the PO's vendor's, which is
what makes `Use this` unconditionally safe.

### 7.2 The policy

```python
class PartPricePolicy:
    @classmethod
    def facts_for(cls, *, part_id, vendor_id, domain_ids) -> PartPriceFactsStruct: ...

    @classmethod
    def facts_for_many(cls, *, part_ids, vendor_id, domain_ids
                       ) -> dict[int, PartPriceFactsStruct]: ...
```

`facts_for_many` must be **O(1) queries in the number of lines** — two bulk queries (recorded,
verified) plus one count, resolved in Python. A per-part loop is the D53 mistake repeated. Filter
by `domain_id__in=domain_ids` **before** ordering, every time.

### 7.3 Wiring

- Chip beside each PO line cost field, rendered **server-side on plain GET** for every existing
  line (`facts_for_many`), and re-fetched by HTMX when the part changes or **the PO's vendor
  changes** (vendor change re-resolves *every* line).
- `Use this` copies the value and stamps `unit_cost_source` (`LAST_PAID` from an `invoiced` source,
  `LAST_ORDERED` from `ordered`, else `QUOTED`) and `unit_cost_asserted_at = observation.observed_at`
  — never today.
- The picker (D92): `format=htmx-picker` on the history URL, opens **unfiltered**, capped at 50 rows
  most-recent-first with verified rows badged, honest about truncation. Picking returns **the naked
  value** plus `unit_cost_source=ESTIMATED` and today's date — no provenance stamp, because the
  picked row may be another vendor's and a false provenance is worse than none.

**Deferred from this phase:** D90's soft lock. It needs a *Use* authority level that has no mapping
in the current permission set; `/admin-persona` owns that. Leave a `# TODO(D90)` where the override
check would sit and log it in `docs/procurement/tech_debt/`.

---

## §8 — Phase 6 and beyond

| Phase | Contents | Blocked on |
| :--- | :--- | :--- |
| 6 | Divergence prompt (D85): ≥1% **and** ≥$0.10 threshold, sticky per-line dismissal, never blocking. *Record* appends a `manual` observation with the buyer's confidence; *Just this order* sets `ESTIMATED`. | Phase 5 |
| 7 | `ordered` writer in `PurchaseOrderContext.place()` — one observation per line, `observed_at = order_date`, `source_po_line` set, `confidence` copied from the line. **Independently useful; can run parallel to 5–6.** | Phase 1 |
| 8 | Derived pricing basis (D88): "$4,210 — could be $3,400 to $5,600" from line confidences. **Not** a `pricing_basis` column (§1.3). | Phase 5 |
| 9 | Receipt reconciliation, `invoiced` writer, source weighting, variance check as a machine comment on the PO's Event. | Package-receipt UI (does not exist) |

Part-detail pricing card: take **option B** from [page_set.md](page_set.md) — `hx-get` include —
and note the F5 caveat in the template comment. Vendor detail gains a "Prices from this vendor"
section off `ppo_vendor_recent_idx`. Part-create success gains a *click*, never a redirect.

---

## §9 — Definition of done for the first cut (Phases 1–4 + 7)

- [ ] `refresh_project.py` runs clean; `manage.py check` clean.
- [ ] A user with `buy` can paste a column of costs against recent parts and save them in one
      transaction, and gets told which rows were dropped for having no price.
- [ ] A user **without** `buy` sees no banner, no grid, and gets a 403 on POST.
- [ ] A user without `price_establish` cannot write `is_verified=True` by any path, including a
      forged POST field.
- [ ] An observation in a domain the actor cannot see never appears in any read, on any page.
- [ ] The unpriced queue finds a part whose breadcrumb was lost (delete the session row and confirm).
- [ ] Every page renders identically on F5 with JS disabled.
- [ ] Placing a PO writes one `ordered` observation per line.
- [ ] `dev_tools/memory.md` gets one line per phase landed.

## §10 — Explicitly not in scope

No `parties/` app extraction. No currency conversion. No catalog import. No quantity-break
resolution. No observation edit or delete screen (append-only). No per-row vendor override on the
grid. No cross-part bulk adjustment. No `pricing_basis` column. No price approval workflow.

---

## §11 — Codebase verification (2026-08-10)

Every anchor this plan names was checked against the working tree before the build started. It holds.
Re-run this list if the plan sits unbuilt for long — a build plan whose paths have rotted is worse
than none, because it fails slowly.

| Anchor the plan depends on | Where it actually is |
| :--- | :--- |
| `accessible_domain_ids(request)` (§1.5) | `presentation_layer/tools/procurement_access.py` — wraps `session_domain_ids`, documented empty-list-means-no-rows |
| `require_buy` / `PERM_BUY` | same file; `require_*` raise `PermissionDenied`, never no-op |
| Custom perms declared on the owning model | `PurchaseOrder.Meta.permissions` (`buy`, `purchase_approve`), `PartDemand.Meta.permissions` |
| `Part.is_domain_limited` + mapping (§2.4) | `app/parts/models/core/part.py`; `PartDomainAccessMapping` with `related_name="domain_access_mappings"` and `is_active` — the §2.4 predicate compiles as written |
| `ProcurementValidationError(errors: list[str])` (§4.1) | `control_layer/errors.py` — subclassed by `TransitionRefused`, `AllocationCapExceeded`. Do not add a fourth |
| `PurchaseOrderLine` (§3.4) | `AuditFieldsMixin, SoftDeleteMixin`; `unit_cost = DecimalField(12, 2)`; existing `pol_*` check-constraint naming — match it (`ppo_*`) |
| `PurchaseOrderContext.place()` (Phase 7) | `control_layer/purchase_order_context.py:67`, returns `PropagationReport` |
| `po_wizard_draft.py` (§5) | `presentation_layer/tools/` — the shape `price_grid_draft.py` copies |
| `PartCreationWizardAdaptor` / `...Factory`, `PartBulkUploadFactory` (§4.3, §5) | `app/parts/control_layer/adapters/` and `.../factories/` |
| `procurement/base.html`, `parts/manufacturers/_manufacturer_picker.html` (§6.4) | both present |
| Target dirs for new control-layer files | `adapters/ domain_structs/ factories/ guards/ handlers/ managers/ narrators/` all exist; **`policies/` does not** — §7 creates it, with `__init__.py` |
| `app/procurement/tests/` | contains only `test_persistence_smoke.py`; §4.5 and §5 add the first real suites in this app |
