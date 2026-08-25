# Legacy Application Map

Every legacy dispatching URL, its Flask view, its source file, and its template. The literal
route inventory behind *"the old interface is the specification"*.

**Generated from** `/home/cb/REPOS/asset_management/app/presentation/routes/dispatching/`.

**Supersedes [old_application_map.md](old_application_map.md)**, which is the same inventory
without verdicts or pass assignment. That file is now redundant; its two useful extras — Flask
endpoint names and the POST-redirect annotations — are folded in below.

---

## 0. How to use this

Find the screen you are porting, open the source and template it names, and **check the verdict
column before writing anything**. Then check [design_drift.md](design_drift.md) for the concept
changes on that screen.

| Verdict | Meaning |
| :--- | :--- |
| **PORT** | Layout is the specification. Rebuild the substance |
| **PORT, RETARGET** | Screen survives, but it now operates on a different record |
| **MERGE** | Several legacy screens collapse into one |
| **DROP** | The concept is gone. No replacement |
| **REFERENCE** | Do not port. Read only if you need the semantics |

**Pass** is the build phase: 1 = now ([build_phase_3_ui.md](build_phase_3_ui.md)), 2 = deferred.

**Flask endpoint names** are `dispatching.<view>` — e.g. `dispatching.templates_list`. The view
column below gives the function name; prefix it with `dispatching.` for the `url_for` name.
Widgets use `dispatching_widgets.<view>`.

**POST-only routes render nothing** — they redirect, or return an HTMX partial. Rows with `—` in
the template column are those.

### 0.1 Paths

| | |
| :--- | :--- |
| URL prefix | `/dispatching` — widgets at `/dispatching/widgets` |
| Routes | `/home/cb/REPOS/asset_management/app/presentation/routes/dispatching/` |
| Templates | `/home/cb/REPOS/asset_management/app/presentation/templates/` |

Source and template columns are relative to those two roots.

---

## 1. Templates — PASS 1

Source: `template_request/templates.py`

| URL | Methods | View | Template | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| `/templates` | GET | `templates_list` | `dispatching/templates/list.html` | **PORT.** Add revision-state and head columns |
| `/templates/new` | GET, POST | `templates_new` | `dispatching/templates/form.html` | **PORT, RETARGET.** Opens a working draft; commit creates the lineage and revision 1 |
| `/templates/<id>` | GET | `templates_detail` | `dispatching/templates/detail.html` | **PORT.** Add revision history, usage, state banner |
| `/templates/<id>/edit` | GET, POST | `templates_edit` | `dispatching/templates/form.html` | **PORT, RETARGET.** Becomes the **session draft editor**. Writes nothing until commit |
| `/templates/<id>/delete` | POST | `templates_delete` | — | **PORT, RETARGET.** Discards the **session** draft. Nothing is deleted from the database |
| `/templates/<id>/revision` | POST | `templates_create_revision` | — | **SPLIT IN TWO.** Opening a working draft from the head, and committing it as a revision, are separate actions with separate permissions |
| `/templates/<id>/copy` | POST | `templates_copy_independent` | — | **PORT.** New lineage at revision 1. Legacy got the concept right |
| `/templates/<id>/deprecated` | POST | `templates_set_deprecated` | — | **PORT, RETARGET.** Becomes lineage-wide retire/reinstate with a required reason |
| `/api/templates/<id>/prefill` | GET | `templates_prefill_api` | — | **PORT, RETARGET.** Resolves the **head** revision |

> **Correction worth noting.** Legacy is not as bare as it looked. `revision`, `copy`, and
> `deprecated` routes all exist — POST-only actions with no screens behind them, no working
> draft, no commit event, no change note, and no head enforcement. Revisioning was *sketched*,
> not absent. The endpoints are a reasonable starting shape; the workflow around them is what
> [1_dispatch_templates.md](1_dispatch_templates.md) rebuilds.
>
> **The bigger change is invisible in this table:** legacy edits a template row directly. The
> new editor holds everything in a session working draft and writes one revision on commit, so
> adding four items produces one version rather than four.

### 1.1 Template requirement search fragments

Source: `searchbars.py`

| URL | View | Template | Verdict |
| :--- | :--- | :--- | :--- |
| `/search-bars/template-filter/skills` | `search_bars_template_filter_skills` | `dispatching/templates/_filter_skills_results.html` | **PORT** as an HTMX fragment |
| `/search-bars/template-filter/capabilities` | `search_bars_template_filter_capabilities` | `dispatching/templates/_filter_capabilities_results.html` | **PORT** |
| `/search-bars/template-filter/parts` | `search_bars_template_filter_parts` | `dispatching/templates/_filter_parts_results.html` | **PORT, RETARGET.** Now a material requirement |

---

## 2. Skills — PASS 1

Source: `management/skills.py` and `management/routes.py`

| URL | Methods | View | Template | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| `/management` | GET | `management_portal` | `dispatching/management/index.html` | **PORT** as the module landing page |
| `/management/skills` | GET | `skills_catalog` | `dispatching/management/skills/index.html` | **PORT** |
| `/management/skills/create` | GET, POST | `create_skill` | `dispatching/management/skills/form.html` | **PORT** |
| `/management/skills/<id>/edit` | GET, POST | `edit_skill` | `dispatching/management/skills/form.html` | **PORT as a page.** The legacy modal at `skills/modals/edit_skill.html` is **DROPped** |
| `/management/skills/view` | GET | `view_user_skills` | `dispatching/management/skills/view_assignments.html` | **PORT** |
| `/management/skills/linkage` | GET | `skills_linkage_portal` | `dispatching/management/skills/linkage_portal.html` | **PORT** |
| `/management/skills/user/<id>` | GET | `user_skills` | `dispatching/management/skills/user_assignment.html` | **PORT.** Must be in-page assignment, never a modal |
| `/management/skills/assign` | POST | `assign_skill` | — | **PORT** |
| `/management/skills/remove/<id>` | POST | `remove_skill_assignment` | — | **PORT** |

### 2.1 Shared search fragments

Source: `searchbars.py`

| URL | Template | Pass | Verdict |
| :--- | :--- | :--- | :--- |
| `/search-bars/users` | `dispatching/search_bars/users_results.html` | 1 | **PORT** |
| `/search-bars/skills` | `dispatching/search_bars/skills_results.html` | 1 | **PORT** |
| `/search-bars/capabilities` | `dispatching/search_bars/capabilities_results.html` | 2 | **PORT** |
| `/search-bars/make-models` | `dispatching/search_bars/make_models_results.html` | 2 | **PORT, RETARGET** → asset models |
| `/search-bars/parts` | `dispatching/search_bars/parts_results.html` | 2 | **PORT, RETARGET** → material demands |
| `/search-bars/configuration-templates` | `dispatching/search_bars/configuration_templates_results.html` | 2 | **PORT** |
| `/search-bars/defined-modifications` | `dispatching/search_bars/defined_modifications_results.html` | 2 | **PORT** |

---

## 3. Navigation and portals — PASS 2

Source: `navigation.py`

| URL | View | Template | Verdict |
| :--- | :--- | :--- | :--- |
| `/` | `index` | `dispatching/navigation/index.html` | **PORT** |
| `/my-requests` | `my_requests` | `dispatching/navigation/user_portal.html` | **PORT, RETARGET** — "my dispatches" |
| `/user-portal` | `user_portal` | *none — 302 alias to `my_requests`* | **DROP.** A legacy alias, not a page |
| `/my-asset-checkouts` | `my_asset_checkouts` | `dispatching/navigation/my_asset_checkouts.html` | **PORT, RETARGET** → my reservations |
| `/dispatcher-portal` | `dispatcher_portal` | `dispatching/navigation/dispatcher_portal.html` | **PORT** — the dispatcher queue |
| `/dispatcher/view-checkouts` | `dispatcher_view_checkouts` | `dispatching/navigation/dispatcher_view_checkouts.html` | **PORT, RETARGET** |
| `/dispatcher/view-checkins` | `dispatcher_view_checkins` | `dispatching/navigation/dispatcher_view_checkins.html` | **PORT, RETARGET** |
| `/assets` | `asset_list` | `dispatching/assets/asset_list.html` | **PORT** |
| `/assets/<id>` | `asset_schedule` | `dispatching/assets/asset_schedule.html` | **PORT.** Becomes the asset reservation calendar — now also the entry point for standalone bookings |

---

## 4. Requests → the Dispatch — PASS 2

Source: `request_manifest/requests.py`

| URL | Methods | View | Template | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| `/requests` | GET | `requests_list` | `dispatching/requests/list.html` | **PORT, RETARGET** → dispatch list |
| `/requests/new` | GET, POST | `requests_new` | `dispatching/requests/form.html` | **PORT, RETARGET** |
| `/requests/<id>` | GET | `requests_detail` | `dispatching/requests/detail.html` | **PORT + EXTEND.** Gains the narration timeline |
| `/requests/<id>/edit` | GET, POST | `requests_edit` | `dispatching/requests/form.html` | **PORT.** Intent lock applies |
| `/requests/<id>/requirements-card` | GET | `request_requirements_card` | `dispatching/requests/_requirements_card.html` | **PORT.** Parts row becomes a material demand |

---

## 5. Outcomes — PASS 2, mostly DROP

Source: `alternative_outcomes/`

| URL | View | Template | Verdict |
| :--- | :--- | :--- | :--- |
| `/requests/<id>/outcome/<type>` | `outcome_create` | `outcomes/{contracts,reimbursements,rejects}/form.html`; `dispatch` redirects to `dispatch_create` | **DROP.** No outcome selection — [4_dispatch_line_items.md](4_dispatch_line_items.md) §2 |
| `/requests/<id>/card/request` | `request_card` | `dispatching/outcomes/request_card.html` | **PORT, RETARGET** — a dispatch summary card |
| `/outcomes/dispatch/<id>/card` | `dispatch_card` | `dispatching/outcomes/dispatch_card.html` | **PORT, RETARGET** → reservation card |
| `/outcomes/contract/<id>/card` | `contract_card` | `dispatching/outcomes/contract_card.html` | **MERGE** → one expense card |
| `/outcomes/reimbursement/<id>/card` | `reimbursement_card` | `dispatching/outcomes/reimbursement_card.html` | **MERGE** → same card |
| `/outcomes/reject/<id>/card` | `reject_card` | `dispatching/outcomes/reject_card.html` | **DROP.** Rejection is on the dispatch |
| `/requests/<id>/visual-dispatch-selector` | `visual_dispatch_selector` | `dispatching/visual_dispatch_selector_stub.html` | **REFERENCE.** A stub in legacy too |
| `/requests/<id>/outcome/dispatch/asset-select-card` | `asset_select_card` | `dispatching/outcomes/asset_select_card.html` | **PORT.** Becomes reservation creation |
| `/requests/<id>/outcome/dispatch/personnel-select-card` | `personnel_select_card` | `dispatching/outcomes/personnel_select_card.html` | **PORT, RETARGET** → crew roster on the dispatch |

### 5.1 Contracts and reimbursements — MERGE into one expense surface

| URL | View | Template | Verdict |
| :--- | :--- | :--- | :--- |
| `/contracts` | `contracts_list` | `dispatching/outcomes/contracts/list.html` | **MERGE** |
| `/contracts/<id>` | `contracts_detail` | `dispatching/outcomes/contracts/detail.html` | **MERGE.** Gains an activity thread |
| `/contracts/<id>/edit` | `contracts_edit` | `dispatching/outcomes/contracts/edit.html` | **MERGE.** **Drop the currency field** |
| `/contracts/<id>/cancel` | `contracts_cancel` | — | **MERGE.** Reason required |
| `/reimbursements` | `reimbursements_list` | `dispatching/outcomes/reimbursements/list.html` | **MERGE** |
| `/reimbursements/<id>` | `reimbursements_detail` | `dispatching/outcomes/reimbursements/detail.html` | **MERGE** |
| `/reimbursements/<id>/edit` | `reimbursements_edit` | `dispatching/outcomes/reimbursements/edit.html` | **MERGE** |
| `/reimbursements/<id>/cancel` | `reimbursements_cancel` | — | **MERGE** |

Also `dispatching/outcomes/{contracts,reimbursements}/form.html` and
`dispatch_view_page_card.html` — merge into one form and one card.

### 5.2 Rejects — DROP entirely

`/rejects`, `/rejects/<id>`, `/rejects/<id>/edit`, `/rejects/<id>/cancel` with
`dispatching/outcomes/rejects/*.html`. Rejection is fields on the dispatch and a dialog that
sets them. There is no rejection record to list, open, edit, or cancel.
→ [2_dispatch.md](2_dispatch.md) §9

---

## 6. Dispatches → Asset Reservations — PASS 2

Source: `dispatch_manifest/dispatches.py`. Legacy "dispatch" here means what is now a
**reservation** — see [design_drift.md](design_drift.md) §1.

| URL | Methods | View | Template | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| `/requests/<id>/outcome/dispatch` | GET, POST | `dispatch_create` | `dispatching/outcomes/dispatches/form.html` | **PORT, RETARGET.** Creates a reservation. Also reachable with no dispatch |
| `/dispatches` | GET | `dispatches_list` | `dispatching/outcomes/dispatches/list.html` | **PORT, RETARGET** → reservation list |
| `/dispatches/<id>` | GET | `dispatches_detail` | `dispatching/outcomes/dispatches/detail.html` | **MERGE** with the asset-record view — §7 |
| `/dispatches/<id>/edit` | GET, POST | `dispatches_edit` | `dispatching/outcomes/dispatches/edit.html` | **MERGE** |
| `/dispatches/<id>/cancel` | POST | `dispatches_cancel` | — | **PORT, RETARGET.** Reason required |
| `/dispatches/<id>/personnel/add` | GET, POST | `dispatches_personnel_add` | `dispatching/outcomes/dispatches/personnel_add.html` | **PORT, RETARGET.** Moves **up to the dispatch** |
| `/dispatches/<id>/personnel/<pid>/remove` | POST | `dispatches_personnel_remove` | — | **PORT, RETARGET.** Same move |
| `/dispatches/<id>/consumables/add` | GET, POST | `dispatches_consumable_add` | `dispatching/outcomes/dispatches/consumable_add.html` | **PORT, RETARGET.** Moves up to the dispatch and becomes a material demand |
| `/dispatches/<id>/consumables/<cid>/remove` | POST | `dispatches_consumable_remove` | — | **PORT, RETARGET** |

---

## 7. Asset records and handover — PASS 2

Source: `dispatch_manifest/dispatch_asset_records.py`. **These merge into the reservation** —
one record per asset, not a line beneath a dispatch. → [3_asset_reservations.md](3_asset_reservations.md) §4

| URL | Methods | View | Template | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| `/dispatch_asset_records` | GET | `dispatch_asset_record_list` | `dispatch_asset_records/list.html` | **MERGE** → reservation list |
| `/dispatch_asset_record/create` | GET, POST | `dispatch_asset_record_create` | `.../create.html` | **MERGE** → reservation create |
| `/dispatch_asset_record/<id>/view` | GET | `dispatch_asset_record_view` | `.../view.html` | **MERGE** → reservation detail |
| `/dispatch_asset_record/<id>/edit` | GET, POST | `dispatch_asset_record_edit` | `.../edit.html` | **MERGE** |
| `/dispatch_asset_record/<id>/delete` | POST | `dispatch_asset_record_delete` | — | **PORT.** Only before any handover |
| `/dispatch_asset_record/<id>/user-check-out` | GET, POST | `dispatch_asset_record_user_check_out` | `.../user_check_out.html` | **PORT.** Accountable person only |
| `/dispatch_asset_record/<id>/user-check-in` | GET, POST | `dispatch_asset_record_user_check_in` | `.../user_check_in.html` | **PORT.** Accountable person only |
| `/dispatch_asset_record/<id>/dispatcher-checkout-verification` | GET, POST | `..._dispatcher_checkout_verification` | `.../dispatcher_checkout_verification.html` | **PORT.** Verifier ≠ self-service actor |
| `/dispatch_asset_record/<id>/dispatcher-return-verification` | GET, POST | `..._dispatcher_return_verification` | `.../dispatcher_return_verification.html` | **PORT.** Meter reads write to asset meter history |

> **These four handover screens are the most faithfully portable in the whole application.**
> The dual-track semantics behind them are deliberately kept — [design_drift.md](design_drift.md) §3.

---

## 8. Manifest link browsers — PASS 2

Source: `request_manifest/manifest_links.py`

| URL | View | Template | Verdict |
| :--- | :--- | :--- | :--- |
| `/dispatch_asset_links` | `dispatch_asset_links_list` | `dispatch_asset_links/list.html` | **DROP.** The link table is gone — the reservation is the record |
| `/dispatch_asset_links/<id>/view` | `dispatch_asset_links_view` | `dispatch_asset_links/view.html` | **DROP** |
| `/dispatch_personnel_links` | `dispatch_personnel_links_list` | `dispatch_personnel_links/list.html` | **REFERENCE.** Crew now lives on the dispatch page |
| `/dispatch_personnel_links/<id>/view` | `dispatch_personnel_links_view` | `dispatch_personnel_links/view.html` | **REFERENCE** |
| `/consumable_links` | `consumable_links_list` | `consumable_links/list.html` | **DROP.** The shared demand queue replaces it |
| `/consumable_links/<id>/view` | `consumable_links_view` | `consumable_links/view.html` | **DROP** |
| `/consumable_links/<id>/return` | `consumable_links_return` | — | **PORT, RETARGET.** Returns go through the shared issuance path |

---

## 9. Widgets and event stubs — PASS 2

| URL | Source | View | Template | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| `/dispatching/widgets/next-and-current-dispatch/<asset_id>` | `widgets.py` | `next_and_current_dispatch` | `dispatching/widgets/asset_dispatch_card.html` | **PORT, RETARGET.** Reads reservations. Belongs on the asset page |
| `/event-components/<slug>/full/<event_id>` | `event_stubs.py` | `event_component_full` | `dispatching/event_components/full.html` | **PORT, RETARGET.** Both dispatches and reservations are events now |
| `/event-components/<slug>/goto_button/<event_id>` | `event_stubs.py` | `event_component_goto_button` | `dispatching/event_components/goto_button.html` | **PORT, RETARGET** |

Also `api.py` — inspect before porting; it predates the current design.

---

## 10. Screens with no legacy route

Nothing to port. Design from the specification.

| New screen | Pass | Specification |
| :--- | :--- | :--- |
| Publish a revision, with change note | 1 | [1](1_dispatch_templates.md) §3.4 |
| Revision history for a lineage | 1 | [1](1_dispatch_templates.md) §4 |
| Draft vs published state banner | 1 | [1](1_dispatch_templates.md) §3.2 |
| Retire / reinstate with reason | 1 | [1](1_dispatch_templates.md) §5 — legacy had a bare deprecated toggle |
| My own certifications | 1 | [5](5_roles_and_permissions.md) §4.4 |
| **Standalone reservation creation** | 2 | [3](3_asset_reservations.md) §2 — no legacy equivalent at all |
| Maintenance hold, for shop leads | 2 | [3](3_asset_reservations.md) §6.1 |
| Reservation change log | 2 | [3](3_asset_reservations.md) §8 |
| **Dispatch narration timeline** | 2 | [4](4_dispatch_line_items.md) §5 |
| Reservation promotion to a dispatch | 2 | [3](3_asset_reservations.md) §11.1 |

---

## 11. Counts

| | Routes |
| :--- | ---: |
| Total legacy dispatching routes | **93** |
| Pass 1 — templates and skills | 21 |
| Pass 2 | 72 |
| DROP, no replacement | 10 |
| MERGE into a smaller surface | 17 |
| New screens with no legacy route | 10 |

The largest single reduction is outcomes: **22 routes across four outcome types collapse into
one expense surface plus a rejection dialog.**
