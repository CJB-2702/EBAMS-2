# New Asset — creation wizard proposal

Goal: a single-page, multi-card wizard for creating an Asset that also lets the user assign it to a data domain, and attach existing capabilities and configurations, in one sitting — following the multi-card wizard pattern in `harness/UX_UI/design_patterns/multi_step_flows.md`.

This is a proposal for discussion — no code implied yet.

## Why this qualifies as a wizard, not a form

Asset has more than one reverse FK a user would plausibly populate in the same sitting: manual `AssetCapability` rows on top of what's inherited, and `AssetConfiguration`/modification assignment (explicitly *not* automatic at creation — see below). Per the trigger rule in `multi_step_flows.md`, that's a wizard.

## What's already automatic (not a card)

- **Domain is not a separate "assign to domain" step** — `domain_id` is one of the four required fields (`AssetFactory.REQUIRED = ("name", "serial_number", "domain_id", "model_id")`) passed at creation, same as any other identity field. There's no post-create reassignment flow implied by the model today, so treat domain selection as part of card 1's identity fields, not a distinct card.
- **`asset_class` is derived, never entered** — it's copied server-side from the selected `model`. Don't put an asset_class field on any card; it should surface as read-only display text once a model is picked (helps the user confirm they picked the right model).
- **Model capability templates auto-copy** — `AssetCreationOrchestrator.create` calls `CapabilityFactory.copy_model_to_asset` at creation time, copying every `ModelCapability` template row onto the new Asset as `AssetCapability` rows. The wizard's capability card should **show these as already-attached** (read-only or lightly editable qty/notes), not let the user re-add them — `CapabilityManager.set_asset_capabilities` explicitly treats inherited rows as untouchable and only reconciles manual additions.
- **Configuration is explicitly deferred by design** — the orchestrator has a standing comment: *"P3: (no default configuration assignment at creation — explicit only)"*. That's a deliberate decision, not an oversight. A configuration card in this wizard is the first place that decision gets a UI — confirm with whoever owns that decision that surfacing it at creation time (rather than as a strictly later, separate action) doesn't contradict the "explicit only" intent. If it's fine, "explicit" just means the user affirmatively picks it in the wizard rather than it happening as a side effect.

## Proposed card order (dependency-first)

1. **Asset identity + domain** (required, always enabled)
   `name`, `serial_number` (unique), `model_id` (drives the denormalized `asset_class`, read-only display once chosen), `domain_id`, optional `status` (defaults "Active"), `config_baseline`, `parent_asset_id` (for hierarchy — sets `root_asset`/`depth_from_root` automatically), meter fields, `tags`. This card alone is enough to produce a valid Asset; everything else is additive.

2. **Capabilities** (unlocks once card 1 validates)
   Two sections:
   - **Inherited** (read-only list) — whatever `copy_model_to_asset` will bring in from the selected model's `ModelCapability` templates. Shown so the user isn't surprised by capabilities appearing they didn't pick.
   - **Additional (manual)** — a picker over the `CapabilityDefinition` catalog, excluding anything already inherited (mirrors `_inherited_definition_ids` exclusion logic in `CapabilityManager`), with qty/notes per selection. These become `AssetCapability` rows via `CapabilityManager.set_asset_capabilities` after the Asset exists. Use the dual-listbox/left-heavy assignment pattern per UX_UI convention — not a modal.

3. **Configuration** (unlocks once card 1 validates)
   A picker over `ConfigurationTemplate` rows scoped to the selected `model` (templates are per-`AssetModel`), producing one `AssetConfiguration` (`documented_at`, `is_current`, `verification_status`, `notes`) via `AssetConfigurationContext.save` / `ConfigurationManager.assign`. If the template has associated `DefinedModification`s applicable to this asset's class/model (per the `applicability/` layer), surface them here too so "actual modifications" can be reconciled in the same sitting rather than as a separate later screen. Given the deliberate "explicit only" framing, this card should default to **collapsed/optional**, not pre-selected or required.

## Session draft shape

```
asset_draft = {
    "identity": {name, serial_number, model_id, domain_id, status, config_baseline, parent_asset_id, meter1..4, tags},
    "manual_capabilities": [{definition_id, qty, notes}, ...],
    "configuration": {template_id, verification_status, notes, modifications: [...]},
}
```

## Open questions to confirm before building

- **Commit granularity**: same question as the parts wizard — does the Asset commit on card 1 (giving a real `asset.id` for the capability/configuration cards to write against directly, consistent with how `AssetCreationOrchestrator` already treats capability-copy and config as sequenced post-root steps within one transaction today), or does the whole wizard stay session-drafted until one final submit? Given the orchestrator already runs capability-copy as a step *after* the Asset row exists in the same transaction, committing card 1 first and running the remaining cards as explicit follow-on writes (still one atomic block per card, matching the orchestrator's existing "named step" shape) seems like the more natural fit than a fully deferred multi-card session draft.
- **Configuration-at-creation vs. later-only**: confirm the "P3 explicit only" comment's intent doesn't mean "must be a separate action after creation" — if it does, drop the configuration card from this wizard entirely and leave it as a detail-page action, same as today.
- **Hierarchy field placement**: `parent_asset_id` is listed on card 1 for now since it affects `root_asset`/`depth_from_root` at creation time, but it may deserve its own small card if the picker UI (searching existing assets) is heavy enough to clutter the identity card.
