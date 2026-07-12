---
type: "Technical Decision"
title: "Phase 2 — Business Concept"
description: "fit.** A configuration template is a named bundle of modifications (a \"lift kit + wheels."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-starter-kit, phase-2-template-applicability]
context_tier: 2
---

# Phase 2 — Business Concept

## What this phase delivers

**Capability: a template knows where it belongs — and refuses ingredients that don't
fit.** A configuration template is a named bundle of modifications (a "lift kit + wheels
+ tint" package). This phase gives the bundle the same fit rules a single modification
has, and adds an early safeguard: you can't drop an ingredient into the bundle that
contradicts where the bundle is meant to go.

## Why it matters (user value, told plainly)

- **Bundles get the same protection as individual modifications.** A "heavy-truck build"
  template can be declared to fit heavy trucks, and the system refuses to assign it to a
  sedan — the same way an individual modification is protected.
- **Bad combinations are caught while building the bundle, not when applying it.** If
  someone tries to add an "engine swap" (which only fits three truck models) to an
  "any-laptop" template, the system stops them right there, at the moment they're
  assembling the bundle — the earliest, cheapest place to catch the mistake.
- **Existing behavior is preserved by default.** Templates today are tied to one specific
  equipment model. New templates keep exactly that behavior out of the box; a person only
  gets the broader options if they deliberately widen the rule.
- **The same trustworthy engine.** Fit is decided by the very same logic built for
  individual modifications, so a template and a modification never disagree about what
  "fits" means.

## How a person experiences it

1. When creating a template, it is automatically scoped to its equipment model — nothing
   changes from today unless they choose to widen it.
2. They can broaden the template's fit (e.g. "any heavy truck") using the same four
   strictness options modifications use.
3. As they add modifications to the template, anything that clearly can't go where the
   template goes is refused immediately, with a plain reason.
4. When the template is later assigned to a real piece of equipment, the fit is checked
   one more time as the final guarantee.

## Who interacts with it

- **People who build configuration templates** — assemble bundles with confidence that
  the parts agree with the whole.
- **People who assign templates to equipment** — protected from putting a bundle on the
  wrong kind of asset.

## What this phase intentionally does **not** do

- No new screens — control layer only ([D9](../decisions.md)).
- It does not re-evaluate fit for *nested* child templates — only the modifications a
  template directly contains.
