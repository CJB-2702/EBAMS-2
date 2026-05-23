# Page hero markup

Canonical HTML for the page-hero container described in [../page_structure.md](../page_structure.md).

```html
<div class="page-hero">
  <div class="page-hero-content">
    <h1 class="page-title">Part Demands</h1>
    <p class="page-subtitle">View and manage part demands across all types</p>
  </div>
  <div class="page-hero-actions">
    <a href="…" class="button">← Back</a>
    <button class="button is-primary">⊕ Create</button>
  </div>
</div>
```

## Notes

- The page hero is **always** the first child of the main content area, immediately under the global breadcrumb / top-nav chrome.
- Buttons inside the hero may be sized up (`0.95rem` font, `0.55em` padding) so they feel prominent — but they keep the standard semantic colours from [../common_buttons.md](../common_buttons.md).
- If a page needs a stat bar, it sits **immediately below** the page hero, in its own row, before any content cards.
- Filters belong in a card *below* the hero, never inside it.
