---
type: "UX Guide"
title: "Search & select patterns — overview"
description: "Seven ways to search, pick, and assign items into a list, and which to reach for. Live demo: /kitchen-sink/design-patterns/list-management/."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Search & select patterns — overview

Seven ways to search, pick, and assign items into a list — all modeled around the same scenario (adding supplier items to a part) so they're directly comparable. Live, interactive demo of all seven: `/kitchen-sink/design-patterns/list-management/` ([template](../../../app/public_app/templates/kitchen_sink/design_patterns/list_management.html)).

> **Note:** any card built around a large search area can double as a create/add form as needed, via a search/create toggle in the card header — not just a pure picker. The **Left-Heavy Assignment Card Pair**, **Top and Bottom Filterable List Table Pair**, and **Top and Bottom Search Select Wide Cards Pair** all demonstrate this toggle live.

The page groups the seven into two families:

- **Left/Right Search & Select Tools** (§1–§3) — the source pool and the result sit side by side.
- **Top and Bottom Selection Tools** (§4–§7) — the search/create step stacks above (or below) the resulting list or detail card.

Every pattern that uses a full filter-form/table layout (§3, §6, §7) can be swapped for the condensed `<search-dropdown>` typeahead + card combo (§4, §5) when the candidate pool doesn't need its own filters — **except the dual listbox (§2)**, which has no search step to swap.

---

## Left/Right Search & Select Tools

| # | Pattern | Shape | Full guide |
| :--- | :--- | :--- | :--- |
| 1 | **List box (single panel)** | One searchable multi-select list, no available/assigned split | [../components/dual_listbox.md](../components/dual_listbox.md) (`<list-box>` is the single-panel half of the dual listbox) |
| 2 | **Dual listbox** | Two equally-weighted panels, bidirectional move buttons | [../components/dual_listbox.md](../components/dual_listbox.md) |
| 3 | **Left-heavy assignment card pair** | 2/3-width searchable pool with its own filters/sort, assigns into a 1/3-width target list | [../design_patterns/left_heavy_assignment_card_pair.md](../design_patterns/left_heavy_assignment_card_pair.md) |

## Top and Bottom Selection Tools

**Naming system.** Patterns §4–§7 are named `<Selection Type> + <Display Type> Combo` (the picker and its results share one card) or `Top and Bottom <Selection Type> <Display Type> Pair` (the picker and its results are two separate stacked cards).

**Selection types:**

- **Select** — implies the `<search-dropdown>` web component.
- **Dropdown** — a standard `<select>` dropdown.
- **Filterable list** — a single input filtering a selectable table.
- **Search select** — a search/filters form paired with a selectable items table.

**Display types:** mini cards, wide cards, table.

Not every combination is built on the live page — e.g. a **Dropdown + Table Combo** (a dropdown with table rows showing your selection, in one card) would follow the same system without appearing here.

| # | Pattern | Shape | Full guide |
| :--- | :--- | :--- | :--- |
| 4 | **Select + mini cards combo** | `<search-dropdown>` typeahead; each pick renders as a small removable tile (reuses the `<file-browser>` tile grid markup) | [../components/search_dropdown.md](../components/search_dropdown.md), [../components/file_browser.md](../components/file_browser.md) |
| 5 | **Select + wide cards combo** | `<search-dropdown>` typeahead; every pick is *appended* (same append-on-pick behavior as §4) as a full-width detail block nested inside the *same* card, underneath the search bar — sharp-cornered content inside the chamfered parent card, distinct from §6's two stacked cards | [../components/search_dropdown.md](../components/search_dropdown.md) |
| 6 | **Top and bottom filterable list table pair** | Top card toggles between a filterable-list search (single input + selectable table) and creating a new item inline; bottom card lists items already assigned as a table | *(demo only — see live page; not yet a standalone guide)* |
| 7 | **Top and bottom search select wide cards pair** | Top card is a search-select (filters form + results table), toggling to the same create form as §6; each pick or create appends a full-width detail card to a stack below | [search_row_cards_pattern.md](search_row_cards_pattern.md) (results layout) |

---

## Choosing one

| Situation | Pattern |
| :--- | :--- |
| Flat multi-select from one list, no two-sided assignment | §1 (list box) |
| Both "available" and "assigned" sets are small enough to browse side by side | §2 (dual listbox) — see [../components/dual_listbox.md](../components/dual_listbox.md) for the full decision table against §1/§3 |
| Candidate pool is large and needs its own filters/sort, picking many at once | §3 or §7 (left-heavy assignment card pair, or top and bottom search select wide cards pair) |
| Picking 0–3 items, one at a time, and a small tile is enough context | §4 (select + mini cards combo) |
| Picking 0–3 items, one at a time, but each needs enough context to confirm before committing | §5 (select + wide cards combo) |
| Users need to search an existing item **or** create a new one inline in the same spot | §6 (top and bottom filterable list table pair) |

For the underlying `<search-dropdown>` vs. plain-HTMX-filter decision that §3/§6/§7 vs. §4/§5 hinges on, see [searchbars.md](searchbars.md).

---

## Common mistakes

- **Using the dual listbox when the pool is large.** Past a few dozen items on either side, dual listbox becomes unscannable — use the left-heavy assignment card pair (§3) instead, which has its own search/filter/sort.
- **Picking §4 or §5 for a large searchable pool.** Both are pickers for a small number of one-at-a-time selections, not a substitute for a filtered table.
- **Building a bespoke "search or create" toggle from scratch.** §6 is a validated pattern; copy its mode-toggle markup rather than reinventing button-pair state.
- **Forgetting the detail card can be swapped.** §3, §6, and §7's search step are visually interchangeable with a `<search-dropdown>` (§4/§5) once the pool is small enough not to need its own filters — don't maintain both forms for the same relation.
- **Misnaming a new pattern.** Before inventing a name, check whether it already fits `<Selection Type> + <Display Type> Combo` or `Top and Bottom <Selection Type> <Display Type> Pair` — most new search-and-select layouts are a recombination of an existing selection type and display type, not a genuinely new shape.
