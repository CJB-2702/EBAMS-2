# Phase 1 — Business Concept

## What this phase delivers

**Capability: a modification knows where it belongs.** Today a standardized modification
(a "lift kit", an "engine swap", a "screen tint") can be recorded against *any* asset,
with nothing to stop an obvious mistake. This phase lets each modification carry its own
rule about which kinds of equipment it fits — and then quietly refuses to be recorded
where it doesn't.

## Why it matters (user value, told plainly)

- **Mistakes are caught at the moment they happen.** When someone tries to record an
  engine modification on a laptop, the system says no — instead of silently storing a
  nonsensical record that someone has to find and clean up later.
- **The rule fits how people actually think about fit.** Sometimes a modification fits a
  whole *category* of equipment ("any heavy truck"); sometimes it only fits a *handful of
  specific variants* ("these three closely-related truck models, not every truck"). Both
  ways of describing fit are supported, and a person picks whichever matches reality.
- **No rule is also a valid choice.** A modification that genuinely goes on anything
  (say, a tracking sticker) can be left unrestricted, and nothing gets in the way.
- **The lists double as a shortcut.** Even when a list isn't acting as a hard rule, it
  still records "the equipment this is usually for", which later makes finding and
  picking the right modification faster.

## How a person experiences it

1. While defining or editing a modification, they choose **how strict** its fit is:
   strict (specific category *and* specific variants), by category only, by a specific
   set of variants, or unrestricted.
2. They list the categories and/or variants it applies to.
3. From then on, whenever anyone records that modification on a real piece of equipment,
   the system checks the fit and blocks anything that doesn't qualify, with a plain-
   language reason.

## Who interacts with it

- **People who maintain the modification catalog** — set each modification's fit rules
  once.
- **People who record modifications on equipment** — are protected from filing a
  modification against the wrong kind of asset; they see a clear refusal, not a silent
  bad record.

## What this phase intentionally does **not** do

- It does not add any new screens — the capability lives in the control layer and is
  exercised through existing entry points (deferred to a later UI effort).
- It does not yet handle **templates** (groups of modifications) — that is the next
  phase, which reuses the very same fit-checking engine built here.
