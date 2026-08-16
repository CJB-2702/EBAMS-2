# Initial prompt

The request that started this kit.

> **Editorial note.** This record was condensed at the developer's request. The opening exchange included
> a naming deliberation that was subsequently withdrawn — the developer reversed the decision and asked
> that the vocabulary under consideration not be carried into this kit, so that if it turns out to be the
> right word it re-emerges on its own merits rather than by anchoring. What survives below is the settled
> request. Git history preserves the original.

---

## Opening request (2026-08-15)

A utility surface under the demands area of the procurement app, over the existing demand graphs:

- Search demand graphs by part id.
- Show over and under quantities.
- Filter easily down to unresolved items.
- Suggest actions to resolve an out-of-balance graph.

Flagged as **critical** by the developer: *"I don't know if my current graphs have the part id stored in
the row data — this column needs to be there."* (Confirmed: it was not there. See `questionnaire.md` M4.)

The system already has a page showing a demand graph as a mermaid swimlane diagram. That page belongs
under this same umbrella.

## Route shape requested

| Route | Purpose |
| :--- | :--- |
| `/procurement/graphs/` | Search graphs |
| `/procurement/graphs/<id>/` | Show one graph's information *(exists today at `/procurement/graph/<id>/`)* |
| `/procurement/graphs/<part-id>/` *(shape TBD)* | A part-scoped utility view across that part's graphs |

The developer was explicit that the third surface was not yet designed: *"I am not sure what this page
should be but it needs to be some sort of utility — let's plan this out. List out some plausible use cases
and information that could be displayed to the user that would make work easier."*

That prompt triggered a business-persona session whose capability matrix became the starting point for
questionnaire sections P1–P3.

## Kit request

> lets make a full build kit for this I need to really think this out

---

## What the initial prompt settled vs. left open

- **Settled:** the umbrella vocabulary is "graphs"; three surfaces are wanted; the existing swimlane detail
  page is re-homed rather than redesigned.
- **Left open, by the developer's own words:** what the part-scoped surface actually *is*.
- **Flagged critical and since confirmed:** graphs could not be queried by part at all. See M4.
