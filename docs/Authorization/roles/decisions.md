# Roles — Design Decisions

This document outlines the **unique design decisions** made in this role system and explains **why** they were chosen. It complements [roles_concept.md](roles_concept.md), which describes *what* roles are. This document addresses the *why* — the trade-offs and reasoning behind constraints that aren't obvious from reading the concept alone.

---

## Decision 1: Multiple roles per user (union model)

**Decision:** a user can hold **zero or more roles simultaneously**, and their effective permission groups are the **union** of all roles.

| Alternative | Trade-off |
| :--- | :--- |
| **Single role per user** | Cleaner constraint, but requires mega-templates like "IT Technician + Facilities Auditor in One". Real people have multiple jobs; bundling them obscures individual responsibilities. |
| **Role stacking with conflict resolution** | Complex — Django's permission system doesn't support denials; conflicts require explicit policy. Union is simpler and reflects reality. |

**Rationale:** real people hold multiple jobs. Jane might be "Technician + Documentation Specialist + Supply Coordinator" — each a distinct responsibility, each with its own permission set. Union semantics mean her effective permissions are "everything she needs for all three jobs."

---

## Decision 2: Single-layer role inheritance (max depth 2)

**Decision:** a role can depend on another role, but only **one level deep**. Specialized roles cannot themselves be parents.

| Alternative | Trade-off |
| :--- | :--- |
| **No inheritance at all** | Simpler schema; but if `DocumentationTechnician` needs everything `Technician` has, you duplicate permission groups (maintenance nightmare). |
| **Arbitrary DAG (deep nesting)** | Fully flexible, but complex — cascade delete becomes a graph traversal, validation harder. Most real org structures don't go past 2 levels. |

**Rationale:** real specializations are shallow. One level of inheritance captures 95% of use cases. The constraint makes validation trivial, cascade delete predictable, and the role tree easy to visualize and explain.

A role can be rebased as needed. A manager has all the permissions of a technician, but if more specialization is needed it likely indicates it's a new base role and should be made independent.

---

## Decision 3: No permission group overlap between parent and child

**Decision:** a specialized role **cannot include the same permission groups as its parent**. Child roles **extend** the parent; they do not duplicate.

| Alternative | Trade-off |
| :--- | :--- |
| **Allow overlap** | Simpler to define roles, but ambiguous semantics: does the child replace, supplement, or override the parent? Silent permission creep risk. |
| **Unrelated roles can overlap (but not parent-child)** | Good compromise — and the one chosen. |

**Rationale:** inheritance should mean "add on top of," not "duplicate." Forbidding overlap prevents the ambiguity of "does this user get the permission group once or twice?"

**Implementation:** validation on role creation/update checks: if this role has a parent, none of its permission groups can be in the parent's group set.

---

## Decision 4: Cascade delete on role dependency

**Decision:** when a base role is deleted from the system, all specialized roles that depend on it are **automatically deleted**. The system shows the user a transitive tree of all dependent roles **before** confirming deletion.

| Alternative | Trade-off |
| :--- | :--- |
| **Soft constraint (warn but allow)** | Leaves orphaned roles in the system; admins later encounter roles with missing parents. |
| **Reassign children to a different parent** | Confusing semantics: `DocumentationManager`? Doesn't make sense. |

**Rationale:** a specialized role **only makes sense in the context of its parent**. The UI must show the full tree of affected roles **before** confirming, so admins see exactly what they're deleting. This is transparent destruction, not silent.

---

## Decision 5: Cascade is directional (remove parent, not child)

**Decision:** when a user has a specialized role and its parent is removed from their role list, the child is **also removed**. When a user has only the child role and it is removed, the parent **stays**.

A child depends on its parent. If the parent is gone, the child is a dangling specialization. Removing a child while keeping the parent is sensible — the user is still a Technician, just not a Documentation Technician.

---

## Decision 6: Role relationship types (primary, specialty, side_job, for_fun)

**Decision:** each role assignment to a user carries a **relationship type** enum: `primary`, `specialty`, `side_job`, `for_fun`.

| Alternative | Trade-off |
| :--- | :--- |
| **No relationship types** | Simpler data model, but all roles look equal in the UI; admin can't tell at a glance "this user's main job is X." |
| **One role designated as "primary"** | Requires a unique constraint; reduces expressiveness for users with co-equal jobs. |

**Rationale:** the goal is storytelling. The relationship type is a one-word label that conveys this. It's not enforced (no unique constraint).

---

## Decision 7: Assignment notes are per-assignment, not per-role

**Decision:** each `UserRole` assignment has a **notes** field explaining why *this user* has *this role*. The role definition itself has a separate description field.

Both are useful: role description explains the role; assignment notes explain the user's assignment. Notes are how auditors later understand "is this access still needed?"

---

## Decision 8: Permission groups are only assigned through roles

**Decision:** a user **cannot** hold a permission group directly. All permission groups must come through a role assignment.

| Alternative | Trade-off |
| :--- | :--- |
| **Allow direct permission group grants** | More flexible, but breaks the role-story principle. |

**Rationale:** keeping the story intact requires that all permissions flow through roles. Every permission group on a user is traceable to a specific role assignment.

---

## Decision 9: Roles are orthogonal to Data Domains

**Decision:** a role has **zero** effect on a user's data scope (which rows they see). Data scope is managed entirely by the domain system.

Mixing role and domain would mean "what you can see depends on who you are and what you're allowed to do" — tempting but wrong. A Technician might need to see assets in Facility A and not Facility B, independent of being a Technician. The domain is the right place for that boundary.

---

## Decision 10: Validation rejects cycles at role-definition time

**Decision:** the system rejects any role dependency that would create a cycle. Cycle detection happens at save time when creating/updating role dependencies, not at runtime.

Schema-time validation is cheaper than runtime traversal and prevents invalid state from ever existing.

---

## Decision 11: No multi-parent roles

**Decision:** a role can have **at most one parent**. A role cannot depend on multiple roles.

| Alternative | Trade-off |
| :--- | :--- |
| **Allow multi-parent (multiple inheritance)** | More flexible, but complex — which parent's groups take precedence? Role trees become DAGs. |

**Rationale:** the max-depth-2 forest structure is easier to reason about, validate, and visualize.

---

## Decision 12: Union resolution (not intersection or override)

**Decision:** when a user holds multiple roles, their effective permission groups are the **union**. No role "overrides" another; no intersection logic.

Union is the simplest and most intuitive — "I'm a Tech AND an Auditor means I can do Tech things AND Audit things."

---

## Summary: the why behind the system

1. **Clarity.** Every permission on a user should trace back to a role assignment with a documented reason. No mystery permissions.
2. **Simplicity.** Single-layer inheritance, union semantics, and no multi-parent keep the system easy to reason about and implement.
3. **Storytelling.** Looking at a user's roles should tell you who they are, what they're responsible for, and why.
