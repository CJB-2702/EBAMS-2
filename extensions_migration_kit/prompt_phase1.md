# Execution Prompt — Phase 1: `detail_extensions` app relocation

**Recommended agent:** `/backend-persona` · **Model:** Sonnet 4.6
*(Mechanical breadth, low reasoning depth — verifiable by grep + rebuild. Escalate to
Opus only if import-graph breakage gets tangled.)*

---

## Paste this to start the phase

> `/backend-persona`
>
> Execute **Phase 1** of the extensions migration kit: relocate + rename the plugin
> framework into a new `app/detail_extensions/` app, clean cut.
>
> **Read first, in order:**
> - `extensions_migration_kit/README.md` (orientation)
> - `extensions_migration_kit/decisions.md` (E1, E2, E4, E5, E8 govern this phase)
> - `extensions_migration_kit/migration_map.md` (the file-by-file spine — Phase 1 rows)
> - `extensions_migration_kit/phase_1_app_relocation/README.md` (scope + exit criteria)
> - `extensions_migration_kit/phase_1_app_relocation/data_relational_plan.md`
> - `extensions_migration_kit/phase_1_app_relocation/control_layer_plan.md`
> - `extensions_migration_kit/phase_1_app_relocation/old_to_new_migration.md` (the checklist — work it top to bottom)
>
> **Do:** move + rename per the migration map (`plugin → extension`, names per E8); give
> each of the 5 concrete extensions a file manifest (E5); remove the concrete-table
> import block from `app/assets/models/__init__.py`; rename the `plugins_provisioned`
> markers → `extensions_provisioned` (kept on the assets tables this phase only);
> **delete** `app/assets/plugins/` and `app/assets/control_layer/plugins/` (E2, clean
> cut). The orchestrator/model-factory may keep a **transient direct call** to the
> relocated provisioner — that is intentional and severed in Phase 2.
>
> **Do NOT (this phase):** add signals, move the `.plugins` managers off the asset
> contexts, move provisioning state to state tables, or touch UI — all later phases.
>
> **Finish:** run `python dev_tools/delete_database_rebuild_models.py --seed` (full DB
> rebuild — project rule; never incremental migrations). Then confirm every exit-criteria
> checkbox in the phase README, especially: `grep -rn "plugin" app/` returns zero
> first-party hits, the old packages are gone, and creating an asset/model still
> provisions extensions (behavior parity).

---

## Reviewer pass (optional)

After the work: `/code-architect-persona` — review the rename for completeness and the
manifest design against `OOP_CONTROL_PATTERNS.md`, then run `/code-review high` on the diff.
