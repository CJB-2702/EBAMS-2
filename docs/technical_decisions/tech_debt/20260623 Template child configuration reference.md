# Tech Debt — Template child should reference a ConfigurationTemplate

**Logged:** 2026-06-23
**Area:** assets / configurations (`TemplateChild`, `ConfigurationTemplate`)
**Status:** Open — interim string column shipped; real reference deferred.

## What we want eventually

A `TemplateChild` (an expected child declared on a `ConfigurationTemplate`) should be able to
point at **another `ConfigurationTemplate`** — i.e. "this build expects, as a child, a unit
built to *that* template." This makes templates **composable** (sub-assemblies / nested build
specs), e.g. a *Scuba Set* template whose expected child *Tank ×2* should itself be built to a
*Tank Standard Build* template.

## Why it's deferred (the two real problems)

1. **Circular import** — largely a *non*-problem. `TemplateChild` already references
   `ConfigurationTemplate` via Django's lazy **string** FK (`"assets.ConfigurationTemplate"`),
   which imports nothing. Adding a second string FK adds no import. The only thing to manage is
   self-recursion inside `ConfigurationTemplateStruct` (a class building itself) — not a module
   import cycle.
2. **Infinite chains** — the *real* problem. Template→child→template→… is a graph. It can form
   **cycles** (A contains B contains A, or A contains itself) and, even when acyclic, a reusable
   sub-template makes it a **DAG** that naive recursion re-expands exponentially (diamonds).
   Any recursive "expand expected structure" walk must terminate safely.

## How to do it properly (when picked up)

- Add a **nullable FK** `child_template → ConfigurationTemplate` (`on_delete=PROTECT`), likely
  with a `CHECK` constraint enforcing *exactly one of* `child_model` / `child_template`.
- Add a **write-time guard** — a `TemplateCompositionPolicy` mirroring
  [`RelationshipPolicy`](../../../app/assets/control_layer/guards/relationship_guard.py): reject
  `child == parent` and reject if `parent` is reachable from `child`'s descendants. Keeps the
  stored graph acyclic by construction.
- Make any recursive reader (`ConfigurationTemplateStruct` expansion) carry a
  `visited: set[template_id]` + a hard **max-depth cap** (terminate + memoize the DAG).

## What shipped instead (interim — 2026-06-23)

To unblock the UI without the graph machinery, `TemplateChild` gained a **plain string column**
`child_configuration` (`CharField`, optional) that simply stores a **template name** as free
text — no FK, no referential integrity, no recursion risk. It is set on the template edit page
via a search dropdown of existing template names but persists only the typed/selected string.

**Migration path:** when the real `child_template` FK lands, backfill it by matching
`child_configuration` strings against `ConfigurationTemplate.name`, then drop the string column.
Treat `child_configuration` as a soft pointer until then — do not build integrity-critical logic
on it.
