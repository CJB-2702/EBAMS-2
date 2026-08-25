# Proto Actions vs Template Actions vs Live Actions

The user's note — *"there is no reference of proto actions just template actions"* —
points at a real omission. The legacy app has **three tiers** of action, not two,
and the kit's presentation mapping only carried the middle one.

---

## The three tiers

| Tier | Legacy table | EBAMS-2 model | Scope | Lifespan | Has a UI? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Proto action** — reusable library step | `proto_actions` (+ `proto_action_tools`, `proto_part_demands`, `proto_action_attachments`) | `ProtoActionItem`, `ProtoActionTool`, `ProtoPartDemand` | Domain-wide library, belongs to no template | Permanent, revisioned | Legacy: list / create / detail. **EBAMS-2: list + thin create only** |
| **Template action** — a step inside one procedure | `template_actions` (+ `template_action_tools`, `template_part_demands`, `template_action_attachments`) | `TemplateActionItem`, `TemplateActionTool`, `TemplatePartDemand` | FK to one `TemplateActionSet` | Immutable once the template is used; changed by revision | Legacy: inside the template detail and builder. EBAMS-2: partial |
| **Live action** — a step being performed | `actions` (+ `action_tools`, `part_demands` via `maintenance_demand_links`) | `Action`, `ActionTool`, `MaintenanceDemandLink` | FK to one maintenance event | Mutable, per job | Legacy: work portal + edit portal. EBAMS-2: partial |

`template_actions.proto_action_item_id` is nullable. That single nullable FK is
the whole relationship: a template step **may** be derived from a proto action,
or may be free-hand. In the seed data 2 of 5 template actions are linked, 3 are
not — which is exactly the situation the template detail page nags about.

---

## What flows down a tier

Creating a template action *from* a proto action copies:

- identity — `action_name`, `description`
- instructions — `instructions`, `instructions_type`
- staffing — `minimum_staff_count`, `required_skills`
- timing — estimated duration, expected billable hours
- `is_required`
- **its children** — every `ProtoActionTool` becomes a `TemplateActionTool`, every
  `ProtoPartDemand` becomes a `TemplatePartDemand`
- safety notes, which then render as the yellow callout on the template detail
  page and again on the live action row in the work portal

The same copy-down happens template action → live action when an event is
instantiated, and proto action → live action directly via the event edit portal's
**From Proto Action** tab.

**This is the reason the library exists.** A proto action is a bundle of
"what it's called, how to do it, who's qualified, how long it takes, what parts
and tools it needs, and how not to get hurt", authored once.

---

## Legacy UI surfaces for proto actions

| Surface | URL | Screenshot | Status in EBAMS-2 |
| :--- | :--- | :--- | :--- |
| Library list — search over name/description/**instructions**, filter by required, sort by name, card grid with duration / tools / parts badges | `/maintenance/proto-actions/list` | `12_proto_actions_list.png` | Exists (`proto/index.html`), needs the badge strip and the instruction-text search |
| Create — 2-column form + parts and tools repeaters | `/maintenance/proto-actions/create` | `14_proto_action_create.png` | Exists (`proto/create.html`) but thin — verify the required toggle, required-skills, billable hours, and both repeaters |
| **Detail** — stat tiles, details, parts, tools, and the **Referenced By Template Action Items** card | `/maintenance/proto-actions/<id>/view` | `13_proto_action_1_view.png`, `42_proto_action_4_view.png` | **Missing. No route, no template.** |
| **Action Creator Portal → From Proto Action tab** | in template builder, event edit portal, and standalone | `33_…`, `35_…`, `34_…` | **Missing** |
| Proto action searchbar endpoints | `/maintenance/searchutils/proto-action`, `/action-creator-portal/search-proto-actions` | — | **Missing** |
| Attachments on proto actions | `proto_action_attachments` table | — | Not in the port; decide whether to keep |
| Build-hub entry buttons **View All Proto Actions** / **Create Proto Action** | `/manager/build-maintenance-templates` | `08_…` | **Missing** (no build hub) |

---

## What to add to the port

1. **Proto action detail route + template**, including the reverse-reference card.
   Without it the library is write-only — you can create protos and never learn
   which templates depend on them. Reverse lookup is
   `TemplateActionItem.objects.filter(proto_action_item=<id>)`, presented as
   `<action name> (from <template name>)` with a link to the template.
2. **The From Proto Action tab** in whatever EBAMS-2 builds as the action source
   picker — for both the template builder and live event editing. This is the only
   path by which a proto action ever reaches real work; without it the tier is
   decorative.
3. **The copy-down helper.** `ActionFactory` already covers template → live
   (`app/maintenance/control_layer/action_factory.py`). Confirm it also covers
   proto → template action and proto → live action, children included.
4. **The advisory callout** on template detail when a template has unlinked
   free-hand steps. It is how the legacy app taught managers to use the library.
5. **Proto action revisioning.** `proto_actions` carries `revision` and
   `prior_revision_id` exactly like templates, and the legacy detail page shows
   `Revision: N/A` for the seeded rows — the columns exist but the UI never
   populated them. Decide explicitly whether EBAMS-2 revisions protos or drops
   the columns; do not inherit the half-built state.

---

## Terminology to fix in the kit

`porting_mapping_plan.md` §4 lists a single `proto_views.py` line with
"Library entrypoints for standard reusable steps" and no detail route. The
mapping should read:

| Legacy route | EBAMS-2 target | Views |
| :--- | :--- | :--- |
| `proto_action_portal.py` + the `main.py` proto detail routes | `presentation_layer/entrypoints/proto_views.py` | `proto_index`, `proto_create`, **`proto_detail`** |
| `search_utils.py` proto endpoint + `action_creator_portal.py` proto tab | `presentation_layer/search/proto_action_search.py` | `ProtoActionSearch` |
