---
type: "Technical Decision"
title: "Visitor Pattern for Custom Event Cards — Design Review"
description: "Status: **proposal / not started**."
tags: [technical-decisions, technical-decision, tech-debt, decisions-pending]
context_tier: 2
---

# Visitor Pattern for Custom Event Cards — Design Review

Status: **proposal / not started**. No code changes accompany this doc.

## The gap this addresses

Every app that creates events writes its own Narrator (`AssetEventNarrator` is
the only one that exists today, in `app/assets/control_layer/narrators/`) to
generate a `(title, description)` string pair, then calls
`Event.objects.create(event_type=EventType.ASSET_MANAGEMENT, ...)` directly.
`EventType` already has seven values — `GENERIC`, `SYSTEM`, `ADMINISTRATION`,
`ASSET_MANAGEMENT`, `INVENTORY`, `DISPATCHING`, `MAINTENANCE` — and there are
stub `*Detail` proxy models for each
(`app/events/models/details/asset_management.py` etc.), but those proxies
carry no fields yet ("Asset-specific fields will be added here once the
assets module is built").

On the read side, every event — regardless of `event_type` — renders through
one template, `app/events/templates/events/fragments/event_card.html`. The
only type-aware logic in it is `if/elif` on `status` and `priority` to pick a
Bulma tag colour. `build_event_card()` in
`app/events/presentation_layer/entrypoints/events.py` always returns the same
`{event, hash, comments}` shape. There is no registry, no per-type template
selection, and no per-type data attached to the event beyond `title` /
`description` text.

So: narration is per-app but ad hoc (copy the Narrator pattern by hand),
and rendering is uniform by construction (there's nothing to dispatch on
yet). The user's stated problem — "there isn't a clear pattern for me to
build custom events" — is really two problems: no contract for **what data**
a module's custom event carries, and no contract for **how that data
renders** into a card. Visitor is a pattern for the second problem; it
doesn't solve the first by itself.

## Prior art: this was already solved once, differently

The sibling Flask project at `/home/cb/REPOS/asset_management` (`app/core` +
`app/maintenance`, among others) hit this exact problem and shipped a
solution — worth reading before designing a new one from scratch.

Its `Event` model (`app/data/core/event_info/event.py`) is structurally the
same idea as this project's: one shared `events` table, an `event_type`
string discriminator, plus an `EventDetailVirtual` abstract base that
concrete per-module detail tables (e.g. `MaintenanceActionSet` in
`app/data/maintenance/base/maintenance_action_sets.py`) inherit from to get
real, fielded one-to-one extension tables (`status`, `priority`,
`assigned_user`, `completion_notes`, `meter_reading`, etc.) — i.e. exactly
what this project's empty `*Detail` proxy stubs
(`app/events/models/details/asset_management.py`) are presumably meant to
become. `MaintenanceNarrator`
(`app/business/maintenance/base/narrator.py`) plays the same role as
`AssetEventNarrator` here.

The rendering side, however, is **not** a Python Visitor — it's
**route-based double dispatch**:

- `app/presentation/routes/event_viewer/event_type_dict.py` is a static
  registry: `EVENT_TYPE_DICT` maps every known event-type string to
  `(owning_module, source_file, description)`, plus a derived
  `EVENT_TYPE_TO_MODULE` and an `event_type_to_slug()` helper. This is
  documentation-as-code more than a dispatcher — it never imports
  per-module rendering logic.
- The core event viewer (`app/presentation/routes/event_viewer/routes.py`,
  `full_detail()`) never renders module-specific HTML itself. For a given
  event it computes `fragment_url = f"/{module}/event-components/{slug}/full/{event_id}"`
  and the page fetches that URL (HTMX-style) to fill in the custom part of
  the card.
- Each owning module exposes its own `event_stubs.py` blueprint
  (`app/presentation/routes/maintenance/event_stubs.py`,
  `.../core/event_stubs.py`, also `assets`, `dispatching`, `inventory`)
  with routes `/event-components/<slug>/full/<event_id>` and
  `/event-components/<slug>/goto_button/<event_id>`. Each one **self-selects**:
  it loads the event, checks `event.event_type` against the slugs it owns,
  and if it's not theirs, returns a shared empty-stub fragment
  (`core/events/event_stub_empty.html`) instead of erroring. If it is
  theirs, it builds module-owned data (via that module's own
  Context/Struct classes) and renders a module-owned template
  (`maintenance/event_components/full.html`,
  `core/events/event_components/asset_created_full.html`, etc.).

The effect is the same as Visitor's goal — each module owns the rendering
logic for the event types it produces, and the dispatcher (the event
viewer) never needs a `case`/`elif` on every type — but the indirection is
an **HTTP route lookup instead of a Python class registry**. This has a
real advantage over an in-process registry: `event_viewer` has **zero
Python import dependency** on `maintenance`, `assets`, `dispatching`, or
`inventory`. Coupling is reduced to "I know your URL shape," not "I import
your class."

**Translating this to Django-Starter-Kit:** the project's existing
`format=` convention (single canonical URL + query parameter, see
`docs/Architecture/patterns/htmx_patterns.md`) governs requests for *one resource at
multiple densities/fragments*, not cross-app composition — a per-module
event-component endpoint isn't a parallel route for the same resource, it's
a distinct resource owned by that module, so adding e.g.
`GET /assets/events/<hash>/card-fragment` alongside the existing canonical
`event_detail`/`event_index` routes doesn't conflict with that rule. This
maps cleanly onto HTMX (`hx-get` to a per-module URL, with the event-type →
module → URL lookup done once in `app/events/`), and it's a proven design,
not a speculative one. It's the stronger default recommendation versus the
in-process registry sketched below — reach for the registry only if
cross-app HTTP round-trips for what's often just a few extra fields turn
out to be worth avoiding.

## What Visitor would look like here

Mapped onto [refactoring.guru's Visitor write-up](https://refactoring.guru/design-patterns/visitor):

- **Element hierarchy** → the seven `EventType` variants (or their `*Detail`
  proxy models, once those carry real fields).
- **`accept(visitor)`** → an `Event.accept(card_visitor)` method, or more
  idiomatically in this codebase, an `EventCardVisitor` that switches on
  `event.event_type` to find the right `visit_*` method (Python has no real
  double dispatch, so this collapses to a single dispatch table rather than
  the GoF two-hop call).
- **ConcreteVisitor** → one visitor per *rendering concern* — e.g. an
  `EventCardContextVisitor` that builds the template context dict per type,
  and separately an `EventCardNarrationVisitor` that the existing Narrators
  could be folded into.
- **`visit_asset_management(event)`**, `visit_inventory(event)`, etc. → one
  method per app, implemented by that app, registered against the shared
  `EventType` enum.

In Python, this is realistically a **registry dict keyed by `EventType`**
mapping to small per-app builder objects — `functools.singledispatch` or an
`if/elif` chain are the other two ways to get the same effect. Visitor's
distinguishing claim is that it's the GoF name for *exactly this kind of
problem* (perform a type-varying operation over a closed-ish hierarchy
without putting the logic in the elements), so it's a reasonable model to
borrow conceptually even if the implementation looks like a registry rather
than a literal `accept()`/`visit()` pair.

## Where it fits the existing suffix vocabulary

None of the existing suffixes (`Struct`, `Context`, `Factory`, `Handler`,
`Manager`, `Policy`, `Validator`, `StateMachine`, `Narrator`, `Adaptor`,
`Orchestrator`) is a clean match. Two reasonable options:

1. **Extend `Narrator`** to own card-building, not just title/description
   text. Today's `AssetEventNarrator.asset_created()` returns
   `tuple[str, str]`; it could instead return a small `EventCardPayload`
   struct (extra fields the card template needs beyond what's on `Event`
   itself), and `EventCardVisitor` would dispatch to
   `<App>EventNarrator.build_card_payload(event)` per type. This keeps event
   text generation and event card data generation in one place per app,
   which matches how Narrator is already scoped ("audit text... for logs
   and UI" — UI is already in its remit).
2. **New suffix, `Renderer`** — a dedicated class per app
   (`AssetEventRenderer`) that owns only the visit-style dispatch, separate
   from Narrator's text-generation job. Cleaner separation of concerns, but
   it's a new word in the vocabulary and another file per app for what might
   be 10-20 lines of logic.

Recommendation: extend Narrator (option 1) unless/until card payloads grow
complex enough to justify splitting. Adding a new suffix should be justified
by actual complexity, not symmetry with the GoF pattern name.

## Mechanics: in-process registry alternative

If a route-based dispatch (above) turns out to be unwanted — e.g. an extra
HTTP round-trip per card feels wasteful for what's a handful of fields, or
cross-app HTTP fetches don't fit how this monolith is deployed — the
in-process registry is the fallback, with the same self-selection idea
implemented as a Python lookup instead of a URL.

Given `Event` is one shared model discriminated by `event_type` (not a real
Python class hierarchy — the `*Detail` proxies are unused stubs), don't
implement `accept()` as a method *on* `Event`. That would mean editing the
shared model every time a new app's event type is added, which is the
inversion-of-control Visitor is supposed to avoid. Instead:

```python
# app/events/control_layer/event_card_registry.py
CARD_VISITORS: dict[EventType, EventCardVisitorProtocol] = {}

def register_card_visitor(event_type: EventType):
    def _wrap(cls):
        CARD_VISITORS[event_type] = cls
        return cls
    return _wrap
```

Each app registers its own visitor at import time (similar to how Django
admin registration works), and `build_event_card()` looks up
`CARD_VISITORS.get(event.event_type, GenericCardVisitor)` instead of an
`if/elif` chain. This keeps `app/events/` ignorant of `app/assets/`,
`app/inventory/`, etc. — the dependency points outward from each app into
events, never the reverse, which matches the existing pattern (events never
imports asset/admin internals; narrators live in the producing app).

## Rendering side: template selection, not just context

A visitor that only varies the *context dict* still funnels every event type
through the same `event_card.html`. If "custom event cards" means visually
distinct cards (different icon, different metadata layout, a domain-specific
mini-widget — e.g. an inventory event card showing a quantity delta, a
dispatch event card showing a route), the visitor's return value needs to
include a **template path**, not just data:

```python
class EventCardVisitResult(NamedTuple):
    template: str         # "assets/fragments/asset_event_card.html"
    context: dict
```

`event_card.html` becomes a thin dispatcher that `{% include result.template
with card=result.context %}`, falling back to the current generic body for
unregistered types. Each app's template extends/includes the shared
`card`/`card-header`/`card-content` shell so density (`format=`) and HTMX
swap-target conventions stay uniform — only the body content varies.

## Trade-offs, applied to this codebase

**Worth it if:**
- More than 2-3 modules actually need visually distinct cards (today only
  `asset_management` has any app-level activity; `inventory`,
  `dispatching`, `maintenance` are enum values with no producing code yet —
  confirm before building infrastructure for unwritten apps).
- The `*Detail` proxy models get real fields, so there's actual per-type
  data to visit over, not just a string already on `Event`.

**Costs to weigh:**
- Every new `EventType` requires touching the registry (the GoF "must
  update all visitors when adding element types" downside) — mitigated by
  the `GenericCardVisitor` fallback, so this is opt-in extensibility, not a
  hard requirement.
- A `functools.singledispatch`-based dispatcher or a plain `if/elif` in
  `build_event_card()` gets ~80% of the benefit with far less ceremony at
  today's scale (one real producing app). Visitor/registry earns its keep
  once there are enough concrete types that the dispatch logic itself
  becomes unwieldy — not before.

## Suggested sequencing if this moves forward

1. Don't build dispatch infrastructure first. Build the second real
   producing app (inventory or maintenance) the way `assets` did it — a
   Narrator, a hard-coded `event_type` at the call site — and see if
   `event_card.html` is already strained by two types worth of `if/elif`.
2. If strain shows up, pick one of the two dispatch mechanisms above (route-
   based self-selecting endpoints per module, modeled on
   `asset_management`'s `event_stubs.py`, or the in-process registry) and
   add a generic/empty fallback so nothing regresses for
   `system`/`generic`/`administration` events that don't need custom cards.
   Lean toward the route-based version first — it's the one with working
   precedent in this codebase's history.
3. Only then revisit whether `*Detail` proxy models need real columns
   (mirroring `MaintenanceActionSet` in the sibling project), or whether
   visit-time payloads computed from existing FKs (e.g. asset name,
   quantity delta) are sufficient without schema changes.
