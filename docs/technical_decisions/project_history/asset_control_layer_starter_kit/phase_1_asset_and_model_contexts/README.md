# Phase 1 — Asset & Model Contexts

The foundation. Every later phase plugs into the seams built here: the aggregate
contexts, the creation **orchestrator**, and the **lifecycle-eventing** hook.

## Goal

Stand up the core control layer for `Asset` and `AssetModel`: read structs,
stateful contexts, creation orchestration, meter history, the parent/child
hierarchy, the denormalized `asset_class` propagation, and asset-lifecycle
eventing via the `events` app.

## In scope

- `AssetModel` creation/edit (was `MakeModel`), incl. `Manufacturer` linking and
  duplicate detection on `(model_name, subtype_name, revision)`.
- `Asset` creation/edit, incl. the required two `ActivityThread`s
  (already in `asset_handler.py`), meters, and the parent/root/depth tree.
- `Asset.asset_class` denormalization kept in sync with `AssetModel.asset_class`.
- Lifecycle events ("Asset Created", "Model Created", key-detail changes) created
  through the events app and linked via a **new `AssetEvent`** model.

## Out of scope (later phases)

Details (P2), configurations (P3), capabilities (P4). The orchestrator should
expose ordered extension points those phases will fill, but Phase 1 leaves them
as no-ops / TODOs.

## Dependencies

- Models: all of `app/assets/models/` (built) + **one new model** `AssetEvent`
  (this phase adds it → run `/db-rebuild`).
- Events app control layer (built) — consumed, possibly minimally extended
  (see [`../event_context_study.md`](../event_context_study.md) §4.4).

## Deliverables

See [`control_layer_plan.md`](control_layer_plan.md). Summary:
`AssetStruct`, `AssetModelStruct`, `AssetContext`, `AssetModelContext`,
`AssetFactory`, `AssetModelFactory`, `AssetCreationOrchestrator`,
`MeterManager`, `AssetHierarchyManager`, `ModelAssetClassPropagationHandler`,
`AssetEventNarrator`, `AssetSerialNumberValidator`, `AssetCreateAdaptor`.

## Exit criteria

- [ ] An asset can be created end-to-end through `AssetCreationOrchestrator` in
      one transaction: two threads + asset + "Asset Created" event + `AssetEvent`
      link, all-or-nothing.
- [ ] An `AssetModel` can be created with manufacturer link and duplicate
      detection; emits "Model Created".
- [ ] Editing key asset fields records a lifecycle event with a field diff.
- [ ] Updating meters writes `MeterHistory` rows and refreshes cached `meter1..4`.
- [ ] Reparenting an asset updates root/depth and writes `AssetParentHistory`.
- [ ] Changing `AssetModel.asset_class` propagates to all child `Asset.asset_class`.
- [ ] All writes live in the control layer; entrypoints are thin.
