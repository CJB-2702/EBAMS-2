# Initial Prompt

## Verbatim system specification

> # 📋 System Specification: Engineering Asset & Supply Chain Registry
>
> ## 1. Business Needs
>
> The primary objective of this system is to bridge the gap between internal engineering
> definitions and external supply chain realities. It tracks internal engineering parts,
> their linear history of design modifications, associated documentation, and the external
> supplier items purchased to fulfill those parts.
>
> ### Key Business Goals:
> * **Searchability:** Users must be able to locate internal parts using internal part
>   numbers, national stock numbers, legacy identifiers, or external manufacturer part numbers.
> * **Traceability:** Every internal part must have a definitive history of modifications,
>   redlines, and associated engineering documents, preserving exactly what was approved at
>   any point in time.
> * **Supplier Independence:** The system must map internal components to one or more external
>   supplier items, tracking supplier-specific documentation (datasheets, quotes) without
>   polluting the internal engineering lifecycle.
>
> ## 2. Data Model & Relationships
>
> ```
> [Manufacturers] ──< [Supplier Items] ──< [Supplier Item Revisions] ──< [Documents]
>                             │
>                             ▲ (Via Supplier ID Reference)
>                             │
>     [Aliases] >─────────────┴─────────────< [Internal Parts] ──< [Part Revisions] ──< [Documents]
> ```
>
> ### Core Entities:
> * **Manufacturers:** Global registry of external companies that manufacture items.
> * **Supplier Items:** The purchasable items sold by vendors. Each record references a single
>   *Manufacturer* and maps directly to an *Internal Part*.
> * **Internal Parts:** The definitive internal engineering records representing an asset or component.
> * **Aliases:** A unified search index table containing alternative names or identifiers. Rows
>   hold a type flag (e.g., Legacy, NSN, MPN) and can optionally hold a reference pointing to an
>   *Internal Part* or a *Supplier Item*.
> * **Part Revisions:** A flat, linear sequence table tracking the engineering lifecycle of an *Internal Part*.
> * **Supplier Item Revisions:** A flat, linear sequence table tracking the lifecycle and updates of a *Supplier Item*.
> * **Documents:** File registries (datasheets, PDFs, drawings) that do not attach directly to
>   parts, but instead attach to specific rows in either *Part Revisions* or *Supplier Item Revisions*.
>
> ## 3. Interaction Patterns & Query Workflows
>
> ### Search & Resolution (Unified Indexing)
> When a user searches an unlabeled part by a Manufacturer Part Number or an old In-House code,
> the system queries the **Aliases** table.
> * If the alias points to an **Internal Part**, it returns that part immediately.
> * If the alias points to a **Supplier Item**, the system resolves the relationship forward to
>   find the associated **Internal Part**.
>
> ### Fetching the Current Asset State
> 1. Query the respective Revisions table filtering by the target Part or Supplier Item ID.
> 2. Order the results by the `Sequence` integer in descending order.
> 3. The top row represents the latest state. Any documents linked to that specific revision
>    sequence are pulled into the user's active view.
>
> ## 4. Summary of Architectural Decisions & Rationale
>
> | Feature Area | Decision Made | Rationale / Why |
> | --- | --- | --- |
> | **Nomenclature** | Renamed "Products" to **Supplier Items**. | Avoids confusion with internal "Finished Goods" the business sells. |
> | **Manufacturers** | Inverted relation: **Supplier Items** point to **Manufacturers**. | A single manufacturer produces many items. |
> | **Search & Numbers** | Copy supplier part numbers into a centralized **Aliases** table. | Single, high-performance search index. |
> | **Documents** | Attached directly to **Revisions**, never directly to Parts/Supplier Items. | Locks documents to a point-in-time state. |
> | **Revision Modeling** | Flat, linear **Sequence + State** model instead of Parent-Child. | Eliminates recursive queries; history like a Git commit log. |
> | **Supplier Isolation** | Distinct **Supplier Item Revisions** table separate from internal part revisions. | Decouples vendor lifecycle from engineering design cycles. |

## Clarifying decisions captured during interrogation (2026-06-23)

Binding answers given by the user during scoping. Each is reflected in [`decisions.md`](decisions.md).

1. **Location.** The system lives in a **new sub-app `app/parts/`** — a root application for
   parts, not an extension of `app/assets/`. ([D1](decisions.md))

2. **Manufacturers are split.** The existing `app/assets/.../manufacturer.py` becomes the
   conceptual **"asset manufacturers"** table. This kit introduces a **separate "part
   manufacturers"** table. Rationale: there will eventually be *many* part manufacturers and
   *few* asset manufacturers, and **asset lookups must stay fast**. A future merge — or
   asset-manufacturer rows pointing at a part-manufacturer row — is explicitly deferred.
   ([D2](decisions.md))

3. **Documents reuse the events file system.** No parts-local file table. Revisions attach
   documents through the existing `events` `File` / `Attachment` / `FileSet` infrastructure.
   ([D5](decisions.md))

4. **Many personas, one root application.** Users include:
   - **Technicians** — mostly need the part number plus an alias or two (fast lookup).
   - **Engineers** — track revisions and coordinate with supply for interoperability.
   - **Supply** — order parts based on maintenance demand.
   - **Sourcing** (potential) — a possible future persona.
   No RBAC/ownership-scoping requirements were specified for this kit — treated as authenticated-only. ([D11](decisions.md))

5. **Mostly new infrastructure.** The legacy app had **only part definitions**. The guiding
   goal: the application generally **only knows about and uses the base Part id** and never
   references supplier items or documentation directly. Future plans: a **BOM management
   tool** and a **configuration allowability tool** — both will consume the base Part id. ([D3](decisions.md))

6. **Aliases auto-populate.** When a Supplier Item is added with its own manufacturer part
   number, an **Alias is created automatically** for that MPN. ([D8](decisions.md))

7. **Aliases don't know about revisions.** Aliases reference a Part or a Supplier Item only —
   never a revision row — on the assumption that an identifier should remain stable
   (interoperable) across revisions. Final call deferred. ([D9](decisions.md), [open_questions.md](open_questions.md))

8. **Kit naming & cadence.** Build the kit under `part_definitions_kit/`. Leave session notes
   and open-ended questions in a doc; the user reviews tomorrow (2026-06-24) and continues work.
