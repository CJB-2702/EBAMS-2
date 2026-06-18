# Brainstorming Session — Asset Plugin Framework (2026-06-04)

A working narrative of the session that recast Phase 2 from a fixed "details"
schema into an extendable **asset plugin framework**. This is the human-readable
companion to [`decisions.md`](decisions.md) D4/D5 and the rewritten
[`phase_2a_plugin_framework/`](phase_2a_plugin_framework/) +
[`phase_2b_first_party_plugins/`](phase_2b_first_party_plugins/) sub-kits.

## Goal

The original Phase 2 ("Asset & Model Details") modeled a closed set of detail
tables — purchase info, vehicle registration, smog, model specs, emissions —
behind a string→model registry, each one hard-known to the asset code. The user's
actual intent is the opposite: a **framework for plugins** where each "detail" is
a self-contained, drop-in unit that the host doesn't have to know about at
authoring time, configurable per asset class and per model the way the old Flask
app provisioned details. Rename **details → plugins** and build the seam.

## How the session ran

It opened as a free brainstorm on "how do plugin systems normally work," then
converted into a Kit Builder run. We established that the existing detail design
already had ~70% of a plugin system's anatomy (a registry, template-driven
applicability, on-create provisioning, an idempotency marker) but was missing the
three things that make a *plugin*: a descriptor that bundles a unit's data +
contract together, the unit owning its own card, and behavior/rules. Interrogation
then narrowed scope hard toward the **framework + control layer**, deferring rules
and UI.

## Key facts established

- **First-party only.** No third-party / pip-installable plugins. Discovery is an
  **explicit registry list**, not import-time self-registration — this keeps the
  D1 "explicit over magical" principle intact while still giving an extension seam.
- **Each plugin owns a concrete typed table** (not a generic JSON/EAV bag). The
  table is reached through a **factory interface**: today the factory creates one
  primary row; the seam is designed so a factory can later build a *cluster* of
  rows hanging off that primary "asset detail" table per plugin.
- **Plugins live as packages** under `app/assets/plugins/<plugin_name>/` — modules,
  not separate Django apps.
- **Minimum contract** = target (asset vs. model) + cardinality (one-to-one vs.
  one-to-many). Everything else (rules, derived status, the asset-page card) is
  deferred; the descriptor/factory just reserve room.
- **On-create hook only** for now — provisioning runs as a named step inside the
  existing creation orchestrator's single transaction.
- **Enablement stays template-driven**, renamed to `asset_plugins_by_asset_class`,
  `asset_plugins_by_model`, `model_plugins_by_asset_class`.

## Decisions reached

- **D4** — Recast "details" as a first-party plugin framework; supersede the
  original Phase 2 detail plan; split Phase 2 into **2a (framework)** and
  **2b (port the concrete plugins)**.
- **D5** — Cardinality moves from the per-template `many_to_one` flag onto the
  **plugin descriptor**; enablement rows become pure on/off `(scope, plugin_key)`
  switches. Model plugins are enabled **by asset class**, not per model.

## Open questions carried into implementation

1. **Cluster factories.** The factory seam is designed for it, but no plugin needs
   a multi-table cluster yet. First real cluster plugin will validate the seam.
2. **Rules & derived status.** Deferred. When added, decide whether they live as
   methods on the descriptor or as a separate `PluginPolicy`/`Validator` per plugin.
3. **The asset-page card.** Out of scope here. The descriptor should grow a
   `card_template` + a render entrypoint when the UI phase lands; the host page
   will iterate enabled plugins and HTMX-lazy-load each card (F5-safe).
4. **Canonical `plugin_key` strings.** Confirm against old seed/template data so
   existing-style enablement rows resolve (carried from the old migration notes).
5. **Do P3 Configurations / P4 Capabilities eventually become plugins too?** They
   resemble plugins (per-class/model copy-on-create). Not folded in now; revisit
   once the framework has proven itself on the ported details.
