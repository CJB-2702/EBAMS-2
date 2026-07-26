# Functionality Set & Role Matrix — for review

**Status: DRAFT for user review (2026-06-24).** This is the document where access decisions are
made. The kit currently builds everything **authenticated-only** ([D11](decisions.md)); the
matrix below is the proposal for who *should* be able to do what once gating is layered on. It
also resolves former **OQ6** (release/redline semantics). Review and edit the cells, then it
becomes binding.

## Personas

| Persona | Core job |
| :--- | :--- |
| **Technician** | Find a part by any number; read its current state and current documents. |
| **Engineer** | Own the internal part definition and its revision history; release majors, issue redlines, attach drawings/change history. |
| **Supply** | Map purchasable supplier items to parts (with a compatibility range); log vendor revision history (datasheets, quotes) as item-thread comments ([D13](decisions.md)); order against demand. |
| **Sourcing** *(potential)* | Curate the manufacturer registry and supplier relationships. Not yet a defined workflow. |

## Functionality × role matrix

Legend: **C** create · **R** read · **U** update · **D** delete/deactivate · — none.
Cells marked **?** are the ones most needing your decision.

| Capability | Technician | Engineer | Supply | Sourcing |
| :--- | :---: | :---: | :---: | :---: |
| Search / resolve a part by any alias | R | R | R | R |
| View Part detail (current rev, docs) | R | R | R | R |
| Create / edit a Part definition | — | C/U | — | — |
| **Release a new major revision** | — | **C ?** | — | — |
| **Issue a redline (minor revision)** | — | **C ?** | — | — |
| Change a revision's `status` (release/obsolete) | — | **U ?** | — | — |
| Attach documents to a Part revision | — | C/U | — | — |
| Comment on a Part or revision | R ? | C | C ? | C ? |
| Register a Part Manufacturer | — | — | C/U | C/U |
| Map a Supplier Item to a Part | — | R | C/U | C/U |
| Set a Supplier Item's compatibility range ([D13](decisions.md)) | — | R | C/U | C/U |
| Log a vendor revision (JSON comment) on a Supplier Item | — | R | C/U | C/U |
| Attach documents (datasheet/quote) to a Supplier Item thread | — | R | C/U | C/U |
| Add a manual alias (NSN / legacy) | — | C ? | C ? | C ? |

## Decisions this matrix must settle (former OQ6 + open cells)

1. **Who may release a major revision** and change `status` to `RELEASED`/`OBSOLETE` — engineers
   only, or supply too for supplier-side rows? Does releasing **lock** the revision (no further
   edits, redlines only)?
user response: do not lock

2. **Redline authorship** — engineers only, or can a technician/supply request a redline?

user response: just engineers

3. **Comment permissions** — can technicians comment (e.g. "found this mislabeled in the field"),
   or read-only?
user response:  allow comments by user

4. **Manual alias creation** — which roles may add NSN/legacy aliases?
user response: allow any elevated non base user role


5. Whether any of this is enforced now or stays views-only with enforcement in a later RBAC pass.

user response: just add comments labeling for now. Ill have a second agent do the actual implementation for RBAC action limitations

Enforce DATA Domain Blocks as needed 
every part should have a boolean is domain limited


---

> **Convention note:** per the kit-builder process, every starter kit must include a
> `functionality_and_roles.md` like this one so access and capability scope are reviewable before
> implementation.
