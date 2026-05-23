# Roles — Examples

Common role assignment scenarios illustrating the rules in [roles_concept.md](roles_concept.md) and [roles_decisions.md](roles_decisions.md).

---

## Scenario 1: simple base role

**Situation:** onboarding a new field technician.

```
User: Alex Chen
├─ Role: Technician (primary)
│  └─ Permission groups: [Asset Lifecycle, Equipment Tracking, Field Work]
│  └─ Notes: "Hired 2026-04-01 as field technician."

Effective: {Asset Lifecycle, Equipment Tracking, Field Work}
```

What Alex can do: view, add, change, delete assets; track equipment; record field work. What Alex cannot do: view compliance audit reports; manage users (those aren't in Technician).

---

## Scenario 2: multiple independent roles (union)

```
User: Blake Moore
├─ Role: Technician (primary)
│  └─ groups: [Asset Lifecycle, Equipment Tracking, Field Work]
├─ Role: Facilities Auditor (specialty)
│  └─ groups: [Audit Reports, Facility Access, Compliance Review]

Effective: {Asset Lifecycle, Equipment Tracking, Field Work, Audit Reports, Facility Access, Compliance Review}
```

Blake holds two **independent, equal responsibilities**. The roles don't interact — it's just "Blake has this role AND that role."

---

## Scenario 3: specialized role (inheritance)

```
User: Casey Rodriguez
├─ Role: Technician (primary)
│  └─ groups: [Asset Lifecycle, Equipment Tracking, Field Work]
├─ Role: Documentation Technician (specialty)
│  └─ Parent: Technician
│  └─ groups: [Documentation Management, Report Generation]

Effective: {Asset Lifecycle, Equipment Tracking, Field Work, Documentation Management, Report Generation}
```

`DocumentationTechnician` **depends on** `Technician`. When assigned:
1. If Casey is not already a `Technician`, the system auto-adds it.
2. Effective groups are: Technician's groups + DocumentationTechnician's groups.
3. There is **no overlap** — DocumentationTechnician does not include Asset Lifecycle, etc.

Removing the role:
- Remove `Documentation Technician`: Casey **keeps** `Technician`.
- Remove `Technician`: the system **also removes** `Documentation Technician` (warns first).

---

## Scenario 4: specialisation hierarchy with multiple children

```
Technician (base)
├─ Documentation Technician
├─ Hardware Specialist
└─ Safety Inspector
```

Different users can specialize along different branches. If `Technician` is deleted, **both** Hardware Specialist and Safety Inspector are cascade-deleted.

---

## Scenario 5: multiple roles including a specialization

```
User: Frank Lopez
├─ Role: Technician (primary)
│  └─ Notes: Primary role; field technician.
├─ Role: Documentation Technician (specialty, parent: Technician)
│  └─ Notes: Added 2026-03-01 for documentation project; review 2026-06-01.
├─ Role: Supply Coordinator (side_job)
│  └─ Notes: Temporary; covering for Sarah during leave (until 2026-05-30).

Effective: union of all three roles' groups.
```

---

## Scenario 6: overlapping permission groups across unrelated roles

```
SupplyTechnician (base)
├─ groups: [Supply Management, Asset Lifecycle]

SupplyManager (base, unrelated)
├─ groups: [Supply Management, Management, Reporting]

User: Grace Thompson
├─ Role: SupplyTechnician (primary)
├─ Role: SupplyManager (specialty)

Effective: {Supply Management, Asset Lifecycle, Management, Reporting}
```

Both roles include `Supply Management`. That's **fine** — no constraint prevents it because they are unrelated roles. Union dedups automatically.

Contrast with Scenario 3: there, the parent-child relationship would forbid `DocumentationTechnician` from including `Asset Lifecycle` if `Technician` already does.

---

## Scenario 7: removing a role from a user

Before:
```
User: Casey Rodriguez
├─ Role: Technician
├─ Role: Documentation Technician (parent: Technician)
Effective: {Asset Lifecycle, Equipment Tracking, Field Work, Documentation Management, Report Generation}
```

Admin removes `Documentation Technician`.

After:
```
User: Casey Rodriguez
├─ Role: Technician
Effective: {Asset Lifecycle, Equipment Tracking, Field Work}
```

Only the permission groups **unique to** Documentation Technician were removed.

---

## Scenario 8: attempting to remove a parent role (cascade)

Admin removes `Technician` from Casey. UI shows:

```
⚠ Removing role "Technician" will also remove:
  └─ Documentation Technician (depends on Technician)

Confirm removal?
```

On confirm, both roles disappear from Casey.

---

## Scenario 9: deleting a role from the system

Admin deletes the `Safety Inspector` role definition. UI shows all users currently holding it plus any dependent roles:

```
⚠ Deleting role "Safety Inspector" will affect 7 users:
  ├─ Dana Kim
  ├─ Elena Patel
  └─ ... (7 users total)

Also check for dependent roles: None.

Confirm deletion?
```

On confirm, the role is removed from the system and from all 7 users.

---

## Scenario 10: audit review

Admin reviews Grant Wilson's access:

```
User: Grant Wilson
├─ Role: Technician (primary)
├─ Role: Auditor (specialty) — review 2026-06-15
├─ Role: Supply Manager (side_job) — until 2026-05-15

Effective: union of all three.
```

Audit checklist: primary clear? Yes. Specializations documented? Yes (with sunset). Temporary roles have expiration? Yes. All roles justified? Yes (notes). Permission groups match roles? Yes (no drift). Any unusual access? No.

Later (2026-06-20), Auditor sunset date has passed: admin removes the role.

---

## Scenario 11: complex org with multiple role branches

```
Field Operations:    Technician → {Documentation, Hardware, Senior}
Compliance & Audit:  Auditor → {Compliance, Safety}
Administration:      Manager → {Operations Manager}
IT & Infrastructure: IT Support, IT Manager (no specializations)
```

A user can hold roles from multiple independent trees. If Field Operations deletes `Technician`, dependent specializations in that tree are cascade-deleted; roles from other trees are unaffected.
