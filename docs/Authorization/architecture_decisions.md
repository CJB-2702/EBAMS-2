# Authorization architecture — design decisions

This document outlines critical **trade-offs and operational decisions** for the two-gate authorization system (permissions + domains). It complements [architecture_summary.md](architecture_summary.md), which describes *what* the system is. This document addresses the *why* — the constraints and accepted risks behind design choices.

---

## Decision 1: Urgent permission revocation — temporary lockout trade-off

**Decision:** when permissions or domains must be revoked urgently (contractor offboarding, security incident), the system identifies all users with active sessions, determines whether they are affected, and **forcefully refreshes** their session state.

**Accepted consequence:** during the refresh window (typically a few seconds), an affected user may be **temporarily locked out** if their permissions are revoked while they are mid-request.

| Alternative | Trade-off |
| :--- | :--- |
| **Wait until session expiration** | Simpler (no forced refresh), but revocation is delayed until the user logs out or session TTL expires — hours or days. Unacceptable for security incidents. |
| **Per-request permission lookup (no session cache)** | Immediate revocation, but every request hits the database for permission checks. Prohibitive performance cost. |
| **Graceful session invalidation with warning message** | No lockout, but adds operational complexity. Still intrusive. |

**Rationale:** session caching is necessary for performance. Urgent revocation is rare but critical. The few-second lockout is **operationally acceptable** because it is time-bounded, transparent to the user (a single failed request, then re-login prompt), and the only safe way to guarantee immediate revocation without per-request DB hits.

A notification system (audit log, admin alert) should surface when urgent revocations occur.

---

## Decision 2: Domain template assignment — additive by default with smart removal

**Decision:** when a user is assigned a new domain template, new domains are **added** to the user's `UserDomain` set; existing domains are **preserved**. When a template is **removed**, the system checks other active templates; if a domain is still supplied by another, it is **kept**; otherwise removed.

| Alternative | Trade-off |
| :--- | :--- |
| **Rebase by default (replace old template)** | Simpler for single-template users, but destructive for users with multiple templates. Surprising and error-prone. |
| **Permanent accumulation (never remove domains)** | Safe but leads to bloat; auditing becomes harder. |

**Rationale:** real users often have multiple, overlapping domain templates. A technician might hold both *Facility 1 Transportation* (primary role) and *Cross-site Emergency Response* (incident duty). Assigning a third template should not strip the first two. Smart removal ensures multiple templates work intuitively, domains aren't lost due to template reassignment, drift is allowed, and audit is clear.

---

## Decision 3: Role cascade delete — mandatory double verification

**Decision:** when deleting a role that has dependent child roles, the system displays the full transitive tree, requires **explicit double verification**, shows all affected users, and only commits the cascade delete after both verifications.

Cascade delete is destructive and transitive — deleting *Technician* removes it from all users and removes all dependent specializations. Unlike domain removal (which leaves data visible but uneditable), permission removal is a capability loss that may break users' workflows.

| Alternative | Trade-off |
| :--- | :--- |
| **No double verification (warn, single confirmation)** | Faster, but a misclick could trigger mass access revocation. |
| **Soft constraint (warn, allow archival)** | Archival preserves history but leaves orphaned roles in the system. |
| **Prevent cascade entirely** | Forces reassignment of all child roles before parent deletion. Safer, but operationally complex. |

**Rationale:** mass access revocation is rare but high-impact. Double verification is the minimal procedural gate that prevents accidental cascades. The list of affected users serves as a final sanity check.

The UI must display role name, dependent roles, and affected-user count prominently; use a typed-confirmation or multi-button pattern; log the deletion with operator ID, timestamp, and the full tree that was deleted.

---

## Decision 4: Data-access exceptions — manual tracking, actively maintained

**Decision:** routes or views that deviate from the Golden Rule (access is determined by domain membership + permission) are **manually logged** in [data_access_exceptions.md](data_access_exceptions.md).

The exception log is **actively maintained by humans** as the codebase evolves. Code reviews flag new routes that break the rule; the exception is documented or the route is fixed.

| Alternative | Trade-off |
| :--- | :--- |
| **Automated scanning for rule violations** | Catches violations but produces false positives. Easy to ignore. |
| **No tracking; hope engineers remember** | Some violations go undocumented; audit trail is incomplete. |

**Rationale:** the Golden Rule is conceptually simple but enforcement is manual (developers must think about it). The exception log is a human-maintained registry of intentional deviations, which serves three purposes:
1. **Audit:** reviewers can see which routes break the rule and why.
2. **Refactoring target:** routes in the log are candidates for cleanup.
3. **Compliance:** organizations with strict data-access requirements can audit these exceptions during reviews.

Operational cost is low. The log grows slowly; code-review discipline ensures new routes are either compliant or explicitly documented.

---

## Summary: trade-offs accepted

| Decision | Accepted risk | Mitigation |
| :--- | :--- | :--- |
| Urgent revocation | Temporary lockout (few seconds) | Transparent to user; brief; rare; documented in audit log |
| Additive domain templates | Domain bloat if not reviewed | Periodic access reviews; drift tracking visible in UI |
| Cascade delete | Mass permission loss | Double verification UI; affected-user list; audit log |
| Manual exception tracking | Log falls out of sync | Code-review discipline; human curation; not auto-generated |
