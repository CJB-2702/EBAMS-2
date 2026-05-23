# Core entities — domain models and dependencies

This document describes how the primary **core** domain models relate to one another. These models form the foundation of the project: other sub-applications and features should depend on them rather than duplicating parallel concepts.

**Domains** are the **core dependency** for row-level scope across the stack; divisions and organizations group domains for administration without replacing the per-row domain reference. For how scope is assigned to users and enforced at runtime, see [../Authorization/data_ownership.md](../Authorization/data_ownership.md) and [../Authorization/users.md](../Authorization/users.md).

## Auditing and users

Every model listed here is **auditable**: it retains who created the record and when, and who last updated it and when. That auditing implies a dependency on the **base user table** (and any shared auditing mixin or abstract base used for those fields). Sub-applications that extend or reference these models should follow the same auditing pattern for consistency.

## Core entities

| Model | Role |
| :--- | :--- |
| **Divisions** | Top-level grouping of organizations (e.g. regional or business divisions). |
| **Organizations** | Each organization is a **set of domains** used for structure and reporting; different organizations **may share** the same domains (overlap allowed). |
| **Domains** | Atomic scope for data rows and user assignment (physical or logical place — e.g. a facility). **Core dependency:** most scoped business rows reference a domain. |
| **Part definitions** | Catalog or specification of a part type. |
| **Part demands** | A demand for a part, tied to definitions and **domains**. |
| **Events** | Occurrences that can optionally relate to assets. |
| **Assets** | Things you track; tied to **domains**. |
| **Files** | Files or media stored as first-class records. |
| **Attachment subclasses** | One-to-one (or one-row-per-link) mappings from an attachment to another model (for example an event id or an asset id). |
| **Part demand link subclasses** | One-to-one mappings from a part demand to other models (for example back to a maintenance action or dispatch action that generated the demand). |

### Organizational hierarchy (conceptual)

**Division → Organization → Domain**

- A **division** contains **organizations**.
- An **organization** refers to **many domains**; those sets are **not** required to be disjoint across organizations.

**Example:** *California Regional* (division) → *San Diego* (organization) → *Facility 2* (domain).

**Users** are assigned **many domains** in the database; that assignment is reflected in the **session** during use for efficient scoping (see [../Authorization/users.md](../Authorization/users.md)).

## Interaction patterns

### Centred on domain

Most list and detail flows for scoped entities **filter by the caller's effective domains** (and Django model permissions). **Domain** is the repeated foreign key on events, assets, and part demands so queries stay consistent: one join or filter primitive for row scope.

### Prerequisites vs. dependents

- **Domains** and **part definitions** act as **structural prerequisites** where the graph requires them: part demands always need both; events and assets need a domain.
- **Events** can optionally point at an **asset**, which supports timelines and asset-centric views without requiring every event to be asset-bound.

### Extension without generic "god" tables

- **Attachment link subclasses** and **part demand link subclasses** are **narrow, typed join rows** to other apps' concepts. Other sub-applications add a dedicated link model instead of overloading a single polymorphic table, so FK integrity and queries stay explicit.

### Division and organization

**Divisions** and **organizations** are for **grouping and navigation** over domains. They do **not** replace the domain FK on individual business rows; reporting and admin UIs may walk division → organization → domain while row-level scope still keys off **domain** directly.

## Dependency rules

### Must-have relationships

- **Events** must have a **domain**.
- **Assets** must have a **domain**.
- **Part demands** must have a **domain**.
- **Part demands** must have a **part definition**.

**General rule:** **All** scoped business rows in the core model are expected to carry a **domain** unless a type is explicitly global or exempt by design.

So **domains** and **part definitions** are structural prerequisites: events, assets, and part demands are anchored to them where the graph specifies "must have."

### Optional relationships

- **Events** **can have** an **asset** (not required).

### Link tables

- **Attachment link subclasses** connect **attachments** to other entity types (one row per kind of link, as designed).
- **Part demand link subclasses** connect **part demands** to other processes or records (for example maintenance or dispatch), again via dedicated link rows.

## Summary

**Domains** sit at the centre of required references for events, assets, and part demands, and are the **core dependency** for row-level scope across the application. **Divisions** and **organizations** structure how domains are grouped for administration; they do not replace the domain as the FK on individual rows. **Part definitions** anchor part demands. **Events** may optionally reference **assets** for filtering. **Attachments** and **part demands** are extended through small, typed link models so other domain objects can reference files and cross-cutting workflows without collapsing everything into a single generic table.
