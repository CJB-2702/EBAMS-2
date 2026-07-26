# Execution Prompt — Phase 2: signal-driven dependency inversion

**Recommended agent:** `/backend-persona` · **Model:** Opus 4.8
*(Highest subtlety in the kit — transaction/signal timing, post-commit semantics,
silent-failure modes. Do not drop below Opus for this phase.)*

---

## Paste this to start the phase

> `/backend-persona`
>
> Execute **Phase 2** of the extensions migration kit: invert the single
> `assets → detail_extensions` dependency so assets becomes fully ignorant of
> extensions. Provisioning becomes signal-driven and post-commit.
>
> **Prerequisite:** Phase 1 is complete (framework relocated + renamed; the only
> remaining link is the transient provisioner call).
>
> **Read first, in order:**
> - `extensions_migration_kit/decisions.md` (E3 = signals, E7 = state tables; D8 in the sibling kit)
> - `extensions_migration_kit/phase_2_signal_inversion/README.md` (scope + exit criteria)
> - `extensions_migration_kit/phase_2_signal_inversion/data_relational_plan.md`
> - `extensions_migration_kit/phase_2_signal_inversion/control_layer_plan.md` (the signal seam + receiver + provisioner reshape)
> - `extensions_migration_kit/phase_2_signal_inversion/old_to_new_migration.md` (the checklist)
>
> **Do:** add `app/assets/signals.py` (`asset_created`, `asset_model_created`); emit each
> as the **last statement inside** the creation `transaction.atomic()` (after
> meter/tree/eventing — NOT `post_save`); remove the transient provisioner calls/imports
> from assets; connect receivers in `detail_extensions/apps.py` `ready()` that schedule
> provisioning via `transaction.on_commit` (capture the owner **pk**, re-fetch inside the
> provisioner — never the stale instance); add the `AssetExtensionProvisioningState` /
> `ModelExtensionProvisioningState` tables and **drop** the `extensions_provisioned`
> columns from `asset`/`asset_model`; move `.plugins` off the asset contexts into new
> `AssetDetailExtensionContext` / `ModelDetailExtensionContext`; remove
> `extensions_provisioned` from the asset/model structs.
>
> **Resolve the carried-over open question:** how `actor` is determined in a post-commit
> context (request user may be gone) — pass an actor id through the signal kwargs or
> resolve a system actor. Decide and note it.
>
> **Do NOT (this phase):** build any UI — that is Phase 3.
>
> **Finish:** full DB rebuild + seed. Then verify the exit criteria, especially:
> `grep -rn "detail_extensions" app/assets/` returns **zero**; a factory that raises in
> provisioning leaves the asset committed (no rollback coupling); the receiver fires
> post-commit only on success; backfill is idempotent via the state table.

---

## Reviewer pass (strongly recommended for this phase)

`/code-architect-persona` then `/code-review high` (or `ultra`) on the diff — focus on
signal timing, the `on_commit` closure capturing pk-not-instance, transaction boundaries,
and that no assets code imports the extensions app.
