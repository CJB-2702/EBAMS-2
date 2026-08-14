---
type: "UX Guide"
title: "Page structure: shell, hero, sidebars, stat bars"
description: "Every page in the application sits inside the same chrome."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Page structure: shell, hero, sidebars, stat bars

Every page in the application sits inside the same chrome. This document specifies that chrome and the three primary page patterns it supports.

---

## Global chrome

- **Breadcrumbs:** every page includes a trail back to the root of the application. The first crumb is the app or product name (not a generic "Home"). Error pages (403/404/500) should include breadcrumbs when feasible so users can recover context.
- **Page title:** pair breadcrumbs with a clear `<h1>` in `main` for the current page.

Breadcrumbs live in a shared block extended from the project base template (`templates/base.html`) or an include; markup stays consistent across apps.

---

## Page hero container

Every page has a **page hero** at the top containing the page title, subtitle, and primary action buttons.

**Required structure (in order):**

1. **Top navigation bar** — App brand + portal tabs (consistent across all pages).
2. **Page hero container** — wraps title/subtitle and action buttons:
   - **Left side:** page title (large, bold) + optional subtitle.
   - **Right side:** primary action buttons (Create, Export, Settings, etc.).
   - **Visual accent:** 4px left border in the primary colour.
   - **Layout:** flex container with `space-between` so title and actions are separated.
3. **Quick details / stat bar** (optional) — Below the hero for key metrics (status, counts, health).
4. **Main content area** — Cards, forms, and lists below the hero.

**CSS classes:** `.page-hero`, `.page-hero-content`, `.page-hero-actions`, `.page-title`, `.page-subtitle`. See [design_patterns/page_hero_markup.md](design_patterns/page_hero_markup.md) for the canonical HTML.

**Do not:**

- Put page title and actions inline (side-by-side without space-between).
- Omit the page hero — every page should have consistent header structure.
- Put breadcrumbs inside the hero; breadcrumbs stay in the global chrome above.
- Combine hero with top-level filters on the same row (filters go below in a card).

---

## Navigation architecture

### Top navigation bar
- **Fixed height:** 3rem.
- **Components:** app brand, portal tabs (Events, Administration, Assets, Maintenance, Inventory, Core), global search, user menu.
- **Portal tabs:** clicking opens a second bar (portal dropdown) with context-specific links for that portal.

### Portal dropdown
- **Trigger:** click a portal tab.
- **Behaviour:** opens below the top nav with sub-links for the selected portal.
- **Toggle:** clicking the active tab again closes the dropdown.

### Main left sidebar (collapsible)
- **Default state:** expanded on search and index pages; collapsed on work portals.
- **Content:** section-scoped navigation links (e.g. "Roles & Access", "Users", "Data Ownership" for administration).
- **Style:** light background, grouped by section with dividers, active link highlighted with left border and primary colour.
- **Collapse:** hamburger in topnav toggles `.is-sidebar-collapsed` on the shell; grid shrinks from `220px` to `0` width.

### In-page navigation sidebar (work portals only)
- **Default:** visible and prominent on work portal pages.
- **Content:** jump links to sections within the current page.
- **Behaviour:** clicking a link smoothly scrolls the main content area; as the user scrolls, the active link indicator follows the visible section.

---

## Three page patterns

### Work portal
**When to use:** viewing a single record (maintenance event, work order, asset, part demand) with associated metadata, actions, assignments, and related items.

**Key features:**
- Hero wrapper for title + primary actions + quick stats.
- In-page nav for section jumping (prominent and sticky).
- 3/4 + 1/4 split: main details on left, auxiliary info (quick actions, assignment, summary) on the right.
- Scrollable right rail so context stays visible without pinning.
- Section IDs and `scroll-margin` for smooth anchor navigation.

### Search / list page
**When to use:** browsing and filtering a list of records with bulk operations and drill-down into details.

**Key features:**
- Full-width filters card with multi-column search inputs.
- Full-width results table with pagination.
- No right rail (all space for content).
- Collapsible main sidebar (on by default).
- Stat bars for quick counts.

### Index / portal hub
**When to use:** a portal's home page offering multiple role-based or feature-based entry points.

**Key features:**
- Centred hero with icon + title + subtitle.
- Primary CTA card (large, prominent) for the most common action.
- Role/feature cards in a grid (3 across typical).
- Summary stats bar at the bottom showing key metrics.

---

## Scrolling, fixed elements, and grid

Top nav, portal dropdown, and sidebars each scroll/stack independently; the shell's grid columns resize when the main sidebar collapses. Exact z-index stacking order and pixel column widths: [design_patterns/page_grid_values.md](design_patterns/page_grid_values.md).
