# TODO — developer notes, 2026-08-19

Notes left for tomorrow-me. Three open threads, written up as individual docs
in this folder. Nothing here is a decision yet — these are the arguments laid
out so the decision can be made quickly instead of re-derived.

## What the original note said

1. **Issuing a set of demands isn't a clear process.** Adding the demand state
   `issued_without_stock_adjustment` was a good first step, but there is still
   no good way to *find a group of demands and issue them together* without
   the issuing screen having to know about the consumer applications
   (Maintenance, Dispatching). Might have to accept an anti-pattern here.
   Leading idea: add two columns to `PartDemand` — **source activity** and
   **source parent identifier**.

2. **Maintenance application is unreviewed.** A lot was built; none of the
   functional code has been read back. Need to find excessive/duplicate paths,
   confirm the control layer roughly matches the legacy application's shape,
   and confirm the real policy rules line up.

3. **Rebuild the legacy Dispatching application.** Key change from legacy:
   previously it was a check-in/check-out system with a pile of infrastructure
   bolted on (group dispatches, capability requirements, skills, alternative
   outcomes). In practice the business mostly just wants to **reserve an
   asset**. Build the simple reservation system first, then build dispatch as
   an *enhancement of the same table* — the two concepts have effectively
   merged.

Plus: rename the application. See below.

## The docs

| Doc | Thread |
| :-- | :-- |
| [01_demand_issuance_grouping.md](01_demand_issuance_grouping.md) | Issuing groups of demands; the two new `PartDemand` columns |
| [02_maintenance_code_review.md](02_maintenance_code_review.md) | Review plan for the maintenance application |
| [03_dispatching_reservation_first.md](03_dispatching_reservation_first.md) | Reservation-first dispatching rebuild |

## Done in this pass

**Application renamed to CJB-DIODE.**

> **C**onfiguration · **J**obs · **B**uying · **D**ispatching · **I**nventory ·
> **O**wnership · **D**etails · **E**vents

Changed: topnav brand (`shared/topnav.html`, `shared/public_topnav.html`, with
the expansion as a `title=` tooltip), all five public marketing pages
(`pub_home`, `pub_features`, `pub_learn_more`, `pub_pricing`,
`pub_get_started`), the home hero (now `CJB-DIODE` with the expansion strip
under it, `.pub-hero-acronym` in `public_marketing.css`), and a tag-row
acronym breakdown on the Learn More page. The literal `cd ebams2` in the
get-started shell block was left alone — that is a real directory name.

Not renamed (deliberately): the repo folder, the Django project, the
`ebams2` package paths, and `EBAMS-2` references inside `harness/` and
`maintenance_starter_kit/`. Those are code and process identifiers, not
product branding; renaming them is a separate mechanical pass with real
breakage risk and no user-visible payoff.
