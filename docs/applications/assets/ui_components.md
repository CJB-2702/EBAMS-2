---
type: "Domain Doc"
title: "UI Components Plan: Asset Management Core"
description: "Page-by-page layout plan for the Asset Management sub-application's core UI components."
tags: [applications, domain-doc, assets]
context_tier: 2
---

# UI Components Plan: Asset Management Core

## Asset Hierarchy Portal (`/assets/<id>/hierarchy/edit/`)

**Goal:** Allow users to view and modify the parent-child relationships of an asset.
**Layout:**
*   **Page Hero:** Standard `page-hero` displaying the Asset's name and a subtitle indicating "Hierarchy Management". Actions: "Back to Asset".
*   **Body Grid (Full Width):**
    *   **Current Hierarchy Card:** A `pc` (panel card) showing the lineage from the Root down to the current asset, and a tree view of its immediate children.
    *   **Assign Parent Card:** A form allowing the user to select a new parent asset (autocomplete searchbar), or detach it to make it a root asset.
    *   **Add Child Card:** A quick form to attach existing assets as children under this asset.

## Asset Meter History Portal (`/assets/<id>/meter-history/`)

**Goal:** View historical meter readings and submit new ones.
**Layout:**
*   **Page Hero:** Standard `page-hero` displaying the Asset's name and a subtitle "Meter History". Actions: "Back to Asset".
*   **Body Grid (Has Rail):**
    *   **Main Column:**
        *   **Log Reading Card:** A form `pc` for inputting a new meter reading (Value, Date, Unit, Notes).
        *   **History Table Card:** A `pc` containing a table of all historical meter readings for this asset, sorted by date descending.
    *   **Rail Column:**
        *   **Current Meters Card:** Displays the current active meter values (latest readings) as stat tiles for quick reference.
