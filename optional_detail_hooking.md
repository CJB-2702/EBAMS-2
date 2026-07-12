# Optional: Pluggable Detail Hooking (deferred alternative)

> **Status:** NOT ADOPTED — documented for future reconsideration only.
> The `asset_control_layer_starter_kit` builds asset/model creation with an
> **explicit orchestrator** instead (see `asset_control_layer_starter_kit/decisions.md`).
> This file preserves the road not taken so the trade-off is greppable later.

## What this pattern is

A way to let follow-on work fire **automatically when an asset or model is
created**, without the core creation code knowing which subsystems exist.

It comes from the old Flask app (`asset_management`), where
`AssetContext.create()` ran in two phases:

1. **Core:** create the `Asset` row (+ a lifecycle event), commit.
2. **Pipeline:** iterate a class-level list of handler objects and call
   `.execute(asset_id, created_by_id)` on each, committing after each.

The list (`post_create_pipeline`) started empty and was filled **at import
time** by other modules registering themselves:

```python
# capabilities module, at import:
AssetContext.register_post_create(CopyCapabilityTemplatesHandler())
# details module, at import:
AssetContext.register_post_create(CreateDetailRowsHandler())
```

The contract was a small ABC (`PostAssetCreateHandler` /
`PostMakeModelCreateHandler`) with one `execute(entity_id, created_by_id)`
method. Handlers were told never to commit/rollback themselves, to be
idempotent, and that a raised exception would be logged-and-skipped while the
asset survived.

## Why it is attractive

- **Decoupling:** the core asset/model code never imports capabilities,
  details, or configurations. Subsystems opt in.
- **Open/closed extensibility:** a brand-new subsystem can participate in
  creation by registering a handler — no edit to core creation code.
- **Good fit for drop-in / plugin modules** that the core is not allowed to
  know about at authoring time.

## Why it was NOT adopted here

It conflicts with this project's stated control-layer principles
(`docs/Architecture/patterns/oop_control_patterns.md`):

| Principle | How the pipeline violates it |
| :--- | :--- |
| **Explicit over magical** | Side effects are wired by import-time registration, not by readable calls. |
| **No hidden side effects** | "What happens when an asset is created?" can't be answered by reading one file — you must know every module that registered. |
| **One transaction per workflow** | Each handler commits independently, so partial state is normal (asset committed, capabilities silently missing). |
| **Tech debt is greppable** | Execution order depends on import order; failures are swallowed and logged. |

In this codebase the candidate hooks (capabilities, details, configurations)
are **all first-party**, so the decoupling benefit does not outweigh the loss
of explicitness and transactional integrity.

## What we do instead

An explicit **`AssetCreationOrchestrator`** (and a model equivalent) names each
follow-on step and runs them inside **one `transaction.atomic()`** block. Each
subsystem still owns its own `Factory`/`Handler`; only the *coordination* is
centralized and visible.

```python
# illustrative — see the starter kit phases for the real shape
class AssetCreationOrchestrator:
    def create(self, *, post_data, actor):
        with transaction.atomic():
            asset = AssetFactory.create(post_data=post_data, actor=actor)
            DetailRowFactory.create_for_asset(asset=asset, actor=actor)
            CapabilityFactory.copy_templates_to_asset(asset=asset, actor=actor)
            # ...emit lifecycle event via the events app...
        return asset
```

## When to revisit this decision

Reconsider the pluggable pipeline **only if** one of these becomes true:

1. We need to support **third-party / drop-in modules** that the core
   codebase must not import or know about.
2. The number of independent, genuinely-optional creation side effects grows
   large enough that a single orchestrator becomes a churn magnet **and** those
   side effects are acceptably allowed to fail without rolling back the asset.

If revisited, keep the explicit orchestrator as the default and treat the
registry as an *additional* extension seam, not a replacement.
