# Model Diagram

The dispatching data model **as it should be built**, plus the legacy model it replaces.

Column detail lives in the design documents; this is about **shape** — what points at what.

---

## 0. How to read these

| Symbol | Meaning |
| :--- | :--- |
| `\|\|--o{` | **Required** reference — the child must have a parent |
| `\|o--o{` | **Optional** reference |
| `\|\|--\|\|` | One-to-one |

Relationship labels are the field name on the child side. Audit fields (`created_by`,
`updated_by`) are present on every table and omitted everywhere — drawing them turns every
diagram into a hairball centred on the user table.

---

## 1. Target — the whole module

```mermaid
flowchart TD
    subgraph EXT["Other applications"]
        direction LR
        adm["administration — User · Domain"]
        evt["events — Event · Comment · Attachment"]
        ast["assets — Asset · AssetClass · AssetModel · CapabilityDefinition · ConfigurationTemplate · DefinedModification · MeterHistory"]
        prt["parts — Part"]
        prc["procurement — PartDemand"]
        inv["inventory — PartIssue"]
    end

    subgraph DISP["app/dispatching"]
        direction TB
        tpl["dispatch_template — the lineage"]
        rev["dispatch_template_revision — immutable"]
        trq["6 template requirement tables"]
        d["DISPATCH — event_detail_dispatching"]
        req["5 requirement tables + demand link"]
        crew["dispatch_personnel"]
        res["asset_reservation"]
        upd["reservation_update"]
        exp["dispatch_expense"]
        sk["dispatch_skill · user_dispatch_skill"]
    end

    tpl -->|"head revision"| rev
    rev --> trq
    rev -->|"raised from"| d
    d --> req
    d --> crew
    d --> res
    d --> exp
    res --> upd
    sk --> req
    sk --> trq

    d ==>|"MTI"| evt
    res ==>|"MTI"| evt
    exp -->|"activity thread"| evt
    req --> ast
    req --> prt
    req --> prc
    trq --> ast
    trq --> prt
    res --> ast
    exp --> prc
    crew --> adm
    sk --> adm
    prc -.->|"issuance"| inv

    classDef ext stroke-dasharray: 5 5
    class adm,evt,ast,prt,prc,inv ext
```

**Four things this shows that the legacy model could not:**

1. **Reservations hang off the dispatch by an optional link** — and can exist with none.
2. **Both the dispatch and each reservation are events.** Two `MTI` edges, not one.
3. **Templates are two records** — a lineage and its immutable revisions.
4. **There is no outcome table.** Reservations and expenses are siblings under the header.

---

## 2. Target — the dispatch and its line items

```mermaid
erDiagram
    event ||--|| event_detail_dispatching : "MTI"
    core_domain ||--o{ event : "domain"

    administration_user ||--o{ event_detail_dispatching : "requested_for"
    administration_user |o--o{ event_detail_dispatching : "requested_by"
    asset_class ||--o{ event_detail_dispatching : "asset_class"
    dispatch_template_revision |o--o{ event_detail_dispatching : "created_from_revision"
    event_detail_dispatching |o--o{ event_detail_dispatching : "previous_dispatch"

    event_detail_dispatching ||--o{ dispatch_personnel : "dispatch"
    event_detail_dispatching ||--o{ dispatch_expense : "dispatch"
    event_detail_dispatching |o--o{ asset_reservation : "dispatch OPTIONAL"

    administration_user ||--o{ dispatch_personnel : "user"
    procurement_vendor |o--o{ dispatch_expense : "counterparty_vendor"
    administration_user |o--o{ dispatch_expense : "payee"
    event |o--|| dispatch_expense : "activity_thread"
```

**`requested_assets` is not on this diagram** because it is not a reference. It is a free-form
informational list, written once and never synced. → [2_dispatch.md](2_dispatch.md) §4

**Rejection is not on this diagram** because it is not a record. Reason, category, alternative
suggestion, and resubmission fields sit on `event_detail_dispatching` itself.
→ [2_dispatch.md](2_dispatch.md) §9

---

## 3. Target — requirements

```mermaid
erDiagram
    event_detail_dispatching ||--o{ dispatch_requested_capability : "dispatch"
    event_detail_dispatching ||--o{ dispatch_requested_skill : "dispatch"
    event_detail_dispatching ||--o{ dispatch_requested_model : "dispatch"
    event_detail_dispatching ||--o{ dispatch_requested_modification : "dispatch"
    event_detail_dispatching ||--o{ dispatch_demand_link : "dispatch"

    capability_definition ||--o{ dispatch_requested_capability : "capability_definition"
    dispatch_skill ||--o{ dispatch_requested_skill : "skill"
    asset_model ||--o{ dispatch_requested_model : "model"
    configuration_template |o--o{ dispatch_requested_model : "configuration_template OPTIONAL"
    defined_modification ||--o{ dispatch_requested_modification : "defined_modification"
    part_demand ||--o{ dispatch_demand_link : "part_demand"

    dispatch_skill ||--o{ user_dispatch_skill : "skill"
    administration_user ||--o{ user_dispatch_skill : "user"
```

**Material is the odd one.** The other four point at a catalogue. Material points at a **real
demand** in the shared procurement hub, raised the moment the dispatch states the need — not a
private wish list. → [2_dispatch.md](2_dispatch.md) §7

**Configuration template is not its own requirement row.** It rides on `dispatch_requested_model`
as an optional FK, since a configuration means nothing without a model as its subject — there is
no `dispatch_requested_configuration_template` table. → [1_dispatch_templates.md](1_dispatch_templates.md) §6.4

---

## 4. Target — reservations

```mermaid
erDiagram
    event ||--|| asset_reservation : "MTI"
    asset ||--o{ asset_reservation : "asset"
    core_domain ||--o{ event : "domain"
    administration_user ||--o{ asset_reservation : "accountable_person"
    event_detail_dispatching |o--o{ asset_reservation : "dispatch OPTIONAL"

    meter_history |o--o{ asset_reservation : "initial_meter_read"
    meter_history |o--o{ asset_reservation : "final_meter_read"

    asset_reservation ||--o{ reservation_update : "reservation"
    administration_user |o--o{ asset_reservation : "checkout_verified_by"
    administration_user |o--o{ asset_reservation : "return_verified_by"
    administration_user |o--o{ asset_reservation : "user_checked_out_by"
    administration_user |o--o{ asset_reservation : "user_checked_in_by"
```

**Three deliberate shapes here:**

| | |
| :--- | :--- |
| **One asset, one booking** | There is no per-asset line beneath a reservation. The reservation *is* the per-asset record |
| **Two meter references, no meter table** | Meter history belongs to the asset and is written by anything that reads a meter. Dispatching points at the two readings bracketing its booking |
| **Exactly one accountable person** | Crew belongs to the dispatch. The four other user references are handover audit, not accountability |

→ [3_asset_reservations.md](3_asset_reservations.md)

---

## 5. Target — templates

```mermaid
erDiagram
    core_domain ||--o{ dispatch_template : "domain"
    dispatch_template ||--o{ dispatch_template_revision : "template"
    dispatch_template |o--|| dispatch_template_revision : "head_revision"
    dispatch_template_revision |o--o{ dispatch_template_revision : "prior_revision"
    dispatch_template_revision |o--o{ dispatch_template : "copied_from_revision"

    dispatch_template_revision ||--o{ dispatch_template_requested_capability : "revision"
    dispatch_template_revision ||--o{ dispatch_template_requested_skill : "revision"
    dispatch_template_revision ||--o{ dispatch_template_requested_model : "revision"
    dispatch_template_revision ||--o{ dispatch_template_requested_modification : "revision"
    dispatch_template_revision ||--o{ dispatch_template_material_requirement : "revision"
    configuration_template |o--o{ dispatch_template_requested_model : "configuration_template OPTIONAL"

    dispatch_template_revision |o--o{ event_detail_dispatching : "created_from_revision"
```

**The manifest hangs off the revision, never the lineage.** That single arrangement is what
makes a revision immutable, and therefore what makes a dispatch's reference to it permanent.

**There are no draft rows.** Editing happens in a session-held working draft; a revision row is
created once, at commit. Four edits produce one revision.
→ [1_dispatch_templates.md](1_dispatch_templates.md) §3.2

```mermaid
flowchart LR
    h["Head revision 3"]
    s["Working draft — session only"]
    e1["edit"]
    e2["edit"]
    e3["edit"]
    r4["Revision 4 — one row, one transaction"]
    h -->|"load"| s
    e1 --> s
    e2 --> s
    e3 --> s
    s -->|"COMMIT with change note"| r4
```

---

## 6. Legacy — what is being replaced

Accurate for the old system. Useful when reading legacy code or screens.

### 6.1 Legacy request and outcomes

```mermaid
erDiagram
    users ||--o{ dispatch_requests : "requested_for"
    events ||--o{ dispatch_requests : "event_id"
    assets |o--o{ dispatch_requests : "requested_asset_id"
    asset_classes ||--o{ dispatch_requests : "asset_class_id"
    major_locations ||--o{ dispatch_requests : "major_location_id"
    dispatch_request_templates |o--o{ dispatch_requests : "created_from_template_id"

    dispatch_requests ||--o{ dispatches : "request_id"
    dispatch_requests ||--o{ dispatch_contract_details : "request_id"
    dispatch_requests ||--o{ dispatch_reimbursement_details : "request_id"
    dispatch_requests ||--o{ dispatch_reject_details : "request_id"

    dispatches ||--o{ dispatch_assets : "dispatch_id"
    dispatches ||--o{ dispatch_personnel : "dispatch_id"
    dispatches ||--o{ dispatch_consumables : "dispatch_id"
    dispatches ||--o{ dispatch_meter_reads : "standard_dispatch_id"
```

Legacy also carried an **untyped pointer** — `active_outcome_type` plus `active_outcome_row_id`,
an integer with no foreign key, naming which of four outcome tables held the answer. It cannot
be drawn because the database did not know it was a reference.

### 6.2 The five structural changes

```mermaid
flowchart LR
    subgraph OLD["Legacy"]
        direction TB
        o1["dispatch_requests + dispatches"]
        o2["4 outcome tables, one selected"]
        o3["dispatches + dispatch_assets"]
        o4["requested_parts + dispatch_consumables"]
        o5["one template row, locks on use"]
    end
    subgraph NEW["Target"]
        direction TB
        n1["one dispatch record"]
        n2["line items — reservations and expenses"]
        n3["asset_reservation, one per asset, standalone"]
        n4["real part demands in the shared hub"]
        n5["lineage plus immutable revisions"]
    end
    o1 -.-> n1
    o2 -.-> n2
    o3 -.-> n3
    o4 -.-> n4
    o5 -.-> n5
```

Also gone: `major_locations` (Data Domain does that job), `dispatch_meter_reads` (two references
into asset meter history), `dispatch_capabilities` and `asset_dispatch_capabilities` (already
deprecated in legacy; the assets application owns capabilities).

Full narrative in [design_drift.md](design_drift.md). Column-level detail in
[models_review.md](models_review.md).

---

## 7. Reverse references — the form-versus-wizard input

One reverse reference is a form with a section. Two or more is a wizard.

| Record | Reverse references | Verdict |
| :--- | ---: | :--- |
| **Dispatch** | 5 requirements + demand link + crew + reservations + expenses + self | **Wizard.** Six are pool-attachment, so **no modals** |
| **Template revision** | 6 requirement tables | **Wizard** — but session-backed, committing once |
| **Template lineage** | revisions, head, dispatches raised from it | Mostly read-only cards |
| **Asset reservation** | `reservation_update` only | **Form with sections.** The light path stays light |
| **Dispatch skill** | user certifications, plus two read-only "required by" lists | **Simple registry form** |
| Expense, personnel, all requirement rows | none | Plain forms |

---

## 8. Application dependencies

```mermaid
flowchart LR
    disp["app/dispatching"]
    evt["events"]
    adm["administration"]
    ast["assets"]
    prt["parts"]
    prc["procurement"]
    inv["inventory"]
    mnt["maintenance"]

    disp ==>|"MTI, twice — HARD"| evt
    disp ==>|"identity and scoping — HARD"| adm
    disp -->|"6 reference targets"| ast
    disp -->|"1 reference target"| prt
    disp -->|"demand hub"| prc
    disp -.->|"issuance path only"| inv
    disp -.->|"NO COUPLING"| mnt
```

| Application | Coupling |
| :--- | :--- |
| `events` | **Hard.** Both the dispatch and every reservation are events. Requires adding a reservation event type — the only change dispatching forces on another application |
| `administration` | **Hard.** Users throughout; Data Domain is the scoping axis and also absorbs what major-location used to do |
| `assets` | Medium. Six reference targets. **No changes required** — capability expiry was cut |
| `parts` | Light. One reference target |
| `procurement` | Behavioural. Demands are raised and cancelled through the hub |
| `inventory` | Behavioural only. Stock never moves except through the shared issuance path |
| `maintenance` | **None, deliberately.** A maintenance-type reservation is checked against nothing |

**Every edge is outbound.** Nothing points back into dispatching, so it can be built and later
refactored without touching another application's schema — the one exception being the new
event type.
