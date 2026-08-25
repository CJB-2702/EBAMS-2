# Build Phase 3 — UI: Dispatch Templates and Skills

Pass-1 screens only. Two self-contained registries. The dispatch and reservation portal is
**pass 2** and is not built here.

---

## 0. The stance: port the screens, rebuild everything behind them

Phases 1 and 2 said *rebuild, do not port*. **This phase is the exception, and only for
layout.**

| Port from legacy | Rebuild from the design documents |
| :--- | :--- |
| Page inventory — what screens exist | What each screen contains |
| Layout, density, field order, card grouping | Which fields exist |
| Navigation and workflow sequence | State names, actions, buttons |
| Filters, list columns, sort defaults | Filter *dimensions* |

> **Trust the legacy UI on shape. Never on substance.**

Read [design_drift.md](design_drift.md) before opening any legacy template. §2.14 governs this
phase: **the legacy template edit page becomes a session-backed draft editor, and its save
button is not a commit.**

Legacy is also Bootstrap. This is Bulma with sharp corners. Reproduce information architecture,
never visual style.

---

## 1. Reference material

### 1.1 Specification

| Document | Supplies |
| :--- | :--- |
| [application_map.md](application_map.md) | **Every legacy URL, view, source file, and template, with a per-route verdict.** §1 and §2 are this phase |
| [1_dispatch_templates.md](1_dispatch_templates.md) | Everything about the template screens |
| [5_roles_and_permissions.md](5_roles_and_permissions.md) | §4.4 — the permission gate on every screen here |
| [design_drift.md](design_drift.md) | §2.14, §4 |
| [build_phase_2_control_layer.md](build_phase_2_control_layer.md) | Steps 1 and 5 — the verbs these screens call |

### 1.2 Legacy screens — layout reference

**Templates.** Routes at
`/home/cb/REPOS/asset_management/app/presentation/routes/dispatching/template_request/templates.py`

| Legacy template | Full path | Verdict |
| :--- | :--- | :--- |
| Template list | `.../templates/dispatching/templates/list.html` | **PORT LAYOUT.** Add revision state and head marker columns; the legacy lock indicator is gone |
| Template detail | `.../templates/dispatching/templates/detail.html` | **PORT LAYOUT.** Add revision history and usage cards |
| Template form | `.../templates/dispatching/templates/form.html` | **PORT LAYOUT — becomes the session draft editor.** Every field edits the working draft; nothing is written until commit |
| Capability filter results | `.../templates/dispatching/templates/_filter_capabilities_results.html` | **PORT.** HTMX search fragment |
| Skill filter results | `.../templates/dispatching/templates/_filter_skills_results.html` | **PORT** |
| Part filter results | `.../templates/dispatching/templates/_filter_parts_results.html` | **PORT, retarget.** Now a material requirement, not a part wish-list line |

Base path for all: `/home/cb/REPOS/asset_management/app/presentation/templates/`

**Skills.** Routes at
`/home/cb/REPOS/asset_management/app/presentation/routes/dispatching/management/skills.py`
and `.../management/routes.py`

| Legacy template | Full path | Verdict |
| :--- | :--- | :--- |
| Management index | `.../templates/dispatching/management/index.html` | **PORT LAYOUT** as the module landing page |
| Skills index | `.../templates/dispatching/management/skills/index.html` | **PORT LAYOUT** |
| Skill form | `.../templates/dispatching/management/skills/form.html` | **PORT LAYOUT.** Keep `requires_expiry` and certification levels |
| Edit skill modal | `.../templates/dispatching/management/skills/modals/edit_skill.html` | **DISCARD the modal.** Editing a catalogue entry is a page. Modals are for destructive confirmation and single-field capture |
| Linkage portal | `.../templates/dispatching/management/skills/linkage_portal.html` | **PORT LAYOUT** — the skill-to-people surface |
| User assignment | `.../templates/dispatching/management/skills/user_assignment.html` | **PORT LAYOUT.** **Must not be a modal** — house rule |
| View assignments | `.../templates/dispatching/management/skills/view_assignments.html` | **PORT LAYOUT** |
| Skills search results | `.../templates/dispatching/search_bars/skills_results.html` | **PORT** as an HTMX fragment |
| Users search results | `.../templates/dispatching/search_bars/users_results.html` | **PORT** |

**Do not open these.** They belong to pass 2 and reading them now invites drifted concepts:

`.../templates/dispatching/outcomes/**` · `.../templates/dispatching/requests/**` ·
`.../templates/dispatching/dispatch_asset_records/**` ·
`.../templates/dispatching/dispatch_asset_links/**` ·
`.../templates/dispatching/dispatch_personnel_links/**` ·
`.../templates/dispatching/consumable_links/**` · `.../templates/dispatching/navigation/**` ·
`.../templates/dispatching/assets/**`

### 1.3 EBAMS-2 patterns

| Pattern | Path |
| :--- | :--- |
| **Registry scaffold** | `.claude/skills/scaffold-registry/SKILL.md` — covers most of the skills UI |
| Entrypoint style | `app/maintenance/presentation_layer/entrypoints/proto_views.py` |
| Search tool | `app/maintenance/presentation_layer/search/` |
| Template structure | `app/maintenance/templates/maintenance/` |
| Revision-bearing UI | `app/maintenance/templates/maintenance/templates/` |
| HTMX conventions | `harness/Architecture/patterns/htmx_patterns.md` |
| Endpoint patterns | `harness/Architecture/patterns/endpoint_patterns.md` |
| Assignment, never in a modal | `harness/UX_UI/design_patterns/modals.md` |
| Form and card actions | `harness/UX_UI/form_style_guide.md` |

---

## 2. Screens

### 2.1 Skills — build first

Smallest surface, no dependencies, and `scaffold-registry` covers most of it.

| Screen | Permission | Notes |
| :--- | :--- | :--- |
| Skills catalogue list | Skills — Catalogue | HTMX search, category filter, active toggle |
| Skill create / edit | Skills — Catalogue | Name, description, category, `requires_expiry`, `uses_certification_levels`. **A page, not a modal** |
| Skill detail | Skills — Catalogue *or* Dispatching — Read | Certified people; read-only "required by" lists |
| Certify a person | Skills — Certify | Level, dates, certificate number. **In-page assignment panel, never a modal** |
| A person's certifications | Skills — Certify | All skills for one person |
| My certifications | *authenticated* | Everyone sees their own |

**Expiry is displayed, never enforced.** A lapsed certification is shown as lapsed. Nothing
auto-revokes, and nothing blocks.

### 2.2 Templates

| Screen | Permission | Notes |
| :--- | :--- | :--- |
| Template list | Template — Author *or* Dispatching — Read | **Head revisions by default.** Toggle to show superseded and retired |
| Template detail | Template — Author *or* Dispatching — Read | Pre-fill, manifest, revision history, usage count, state banner |
| Start editing | Template — Author | Loads the head into a **session working draft**. Writes nothing |
| **Draft editor** | Template — Author | The legacy form page. **Every control edits the session, not the database** |
| Requirement manifest editor | Template — Author | Five in-page assignment panels plus material requirements — all session-backed |
| Discard draft | Template — Author | Clears the session key. Nothing to delete |
| **Commit revision** | **Template — Commit** | **Change note required.** One revision, however many edits. Refused if the head moved |
| Copy to new template | Template — Author | Seeds a working draft into a new lineage |
| Retire / reinstate | **Template — Commit** | Reason required |
| Revision history | Template — Author *or* Dispatching — Read | The lineage, states, change notes, publishers |

### 2.3 Screens with no legacy equivalent

Legacy revisioning was **sketched, not absent** — see [application_map.md](application_map.md)
§1. `POST /templates/<id>/revision`, `/copy`, and `/deprecated` all exist as bare actions with
no screens behind them, no draft state, no publish event, and no head enforcement.

So four screens are designed fresh, and one existing action gains a real workflow:

| New screen | Legacy state |
| :--- | :--- |
| **Working-draft editor with unsaved-changes state** | Legacy edited rows directly. This is the largest new build in the phase |
| Commit, with change note | No publication event existed at all |
| Revision history | A lineage field almost nobody set |
| Draft-vs-published state banner | Locked / unlocked — the opposite model |
| Retire / reinstate with reason | A bare `deprecated` POST toggle |
| Copy to new template | **The route exists** — `templates_copy_independent`. Legacy had the concept right; it just had no screen |

**The state banner is the highest-value small thing here.** A person editing a template must
know at a glance whether they are changing a draft nobody sees or looking at a published
revision they cannot change.

### 2.4 Module landing page

Port the layout of `.../templates/dispatching/management/index.html`. In pass 1 it links to
templates and skills, with pass-2 destinations either absent or visibly disabled — not broken
links.

---

## 3. House rules this phase will test

| Rule | Where it bites |
| :--- | :--- |
| **Assignment never in a modal** | Certifying a person; attaching requirements to a template. Legacy uses modals for both. In-page panels or dual listboxes |
| **A card renders even when empty** | "No requirements yet", "No one certified yet", "No previous revisions" — never a hidden card |
| **Every state survives a page reload** | Draft editing especially. HTMX layers on top |
| **One canonical URL per resource** | `format=` for density and fragments. No parallel fragment-only routes |
| **Sharp corners** | Legacy is Bootstrap. Do not carry its styling |
| **No multi-line `{# #}` comments** | Filter sections in particular |

---

## 4. Traps

| Trap | Guard |
| :--- | :--- |
| Making the draft editor write to the database | doc 1 §3.2 — four edits must produce one revision |
| Making the editor's save button commit | doc 1 §3.4. Different actions, different permissions |
| Not warning that a draft is unsaved | doc 1 §3.3 — the session is a scratchpad and the UI must say so |
| Showing superseded revisions in the requester's picker | doc 1 §3.3 — head only |
| Porting the lock indicator | design_drift §2.14 — locking is gone |
| Allowing edits to a committed revision anywhere in the UI | doc 1 R1. No admin override |
| Building the template's parts panel as a wish list | doc 1 §6.4 — a material requirement |
| Porting the edit-skill modal | §1.2 |
| Adding capability expiry to skill screens | design_drift §2.11. **User skill expiry stays; asset capability expiry is cut** |
| Opening pass-2 templates "for reference" | §1.2 |

---

## 5. Done when

**Skills**

- [ ] Catalogue list, create, edit, detail
- [ ] Certify a person, in-page, never a modal
- [ ] A person's certifications; my own certifications
- [ ] Expiry displayed, never enforced
- [ ] HTMX search on skills and users

**Templates**

- [ ] List defaults to head revisions, with a toggle
- [ ] Detail shows pre-fill, manifest, revision history, usage, state banner
- [ ] Draft editing is session-backed — the database is untouched until commit
- [ ] The editor makes unsaved-draft state visible at all times
- [ ] Several edits then one commit produces exactly one revision
- [ ] Commit requires a change note and its own permission
- [ ] A commit against a stale head is refused with a clear message
- [ ] Copy-to-new-template
- [ ] Retire and reinstate, reason required
- [ ] Committed revisions unreachable for editing anywhere in the UI

**Both**

- [ ] Every screen enforces its permission from doc 5 §4.4
- [ ] Domain-denied resolves 404, not 403
- [ ] Every screen survives a plain page reload
- [ ] No assignment in a modal; no card hidden when empty
- [ ] Reachable from the module landing page and the topnav
- [ ] `./venv/bin/python manage.py check` passes
- [ ] Side-by-side screenshots, legacy against new, for every ported screen

**Explicitly not in this phase:** the dispatcher queue, dispatch create and edit, review and
planning, assignment, calendars, checkout and return, expenses. All pass 2.
