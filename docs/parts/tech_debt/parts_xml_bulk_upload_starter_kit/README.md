# Parts XML Bulk Upload — Starter Kit

**Status:** deferred (tech debt). Moved here from the repo root on 2026-08-08 — questionnaire was
never completed/interrogated, and the developer chose not to implement this session. Picking this
back up should resume at "fill in `questionnaire.md`," not at the draft plan below.

A backend-only starter kit for a second bulk-import path into the `parts` app: an uploaded XML
document that, in one pass, can create a part's full identity plus its manufacturer/supplier
items **and** express relationships between parts — the thing the existing CSV/paste-grid bulk
upload at `/parts/bulk-upload/` structurally cannot do (it is one flat row per part, with no way
to reference another row). See [initial_prompt.md](initial_prompt.md) for the full seed context,
including the prior CSV bulk-upload work this kit builds on and inherits constraints from.

[implementation_plan_draft.md](implementation_plan_draft.md) is a concrete draft plan sketched in
the same session, before the questionnaire was completed — it picks answers for several open
questions (notably R1/M5's forward-reference and alternate-part-alias question, which it does
**not** actually address) rather than resolving them. Treat it as a running start, not a finished
design — reconcile it against `questionnaire.md` before building.

No phase table yet — phases are proposed after the questionnaire is answered and interrogated.
