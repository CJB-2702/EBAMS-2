---
type: "UX Example"
title: "Page shell — grid and z-index values"
description: "Exact pixel widths and stacking order for the shell described in [../page_structure.md](../page_structure.md)."
tags: [ux-ui, ux-example, examples]
context_tier: 3
---

# Page shell — grid and z-index values

Exact pixel widths and stacking order for [../page_structure.md](../page_structure.md).

## Scrolling and fixed elements

- **Top nav:** fixed to viewport, always visible, z-index 40.
- **Portal dropdown:** fixed below top nav, z-index 30.
- **Main sidebar:** independent scroll within its own column.
- **In-page nav sidebar:** independent scroll within its own column.
- **Main content area (scrollarea):** `overflow-y: auto`, contains the max-width container and all body content. The right rail (on work portals) is *inside* the scrollarea so it scrolls together with main content.

## Container and grid

- **Max-width:** 1200px, centred with auto margins.
- **Grid columns (dynamic):**
  - Default (search, index): `220px [main nav] | 1fr [content]`.
  - Work portal: `220px [main nav] | 180px [in-page nav] | 1fr [content]`.
  - When sidebar collapsed: `0 | [in-page nav] | 1fr` or `0 | 1fr`.
