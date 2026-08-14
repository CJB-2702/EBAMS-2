# BUG — `.card-header-actions` overflows past the card's right edge

**Status:** unresolved, needs follow-up.

## Symptom

On the kitchen sink's "Basic editable content" card
(`/kitchen-sink/` → Card Layouts → first card), the icon-only Edit button
in the card header renders partially off the right edge of the card —
looks visually "cut off" / shifted too far right, clipped by the card's
20px corner chamfer (`corner-shape: bevel` on `.card`, see
`--app-chamfer` in `app/static/css/custom_css.css`).

Confirmed via Playwright bounding-box measurement (not just a screenshot
crop artifact):

```
card1 rect:     {'x': 248, 'right': 1028, 'width': 780, ...}
edit btn rect:  {'x': 992.48, 'right': 1059.97, 'width': 67.48, ...}
```

The Edit button's right edge (1059.97) is ~32px past the card's right
edge (1028) — a real layout overflow, not just corner clipping.

## Root cause (partially diagnosed)

`.card-header-actions` (a flex container holding the View + Edit
buttons) is being sized to 102px by the flex layout in `.card-header`,
but its two children — buttons with `aspect-ratio: 1/1` and
`align-self: stretch` sized to the header's ~67.5px height — need
~135px combined (67.48 × 2). The container doesn't grow to fit its
own content; the buttons overflow it instead.

Added `flex-shrink: 0` to `.card-header-actions` expecting the browser
to stop shrinking it below its content size — **this did not fix it**.
Computed style after the change still reports `width: 102px` even
though `flex-shrink: 0` is confirmed applied (checked via
`getComputedStyle`). So the container's width isn't being shrunk by
flexbox in the usual sense — something about how its width is being
derived is capping it at 102px regardless. Likely candidates not yet
tested:

- The `aspect-ratio: 1/1` + `align-self: stretch` combo on the buttons
  may be creating a sizing dependency loop (button width needs
  container's flex-basis pass, which needs button's hypothetical
  width, etc.) that resolves to something other than "grow to fit."
- `.card-header-actions`'s own width might need an explicit
  `width: max-content` / `width: fit-content` rather than relying on
  default flex-item sizing, since it's nested inside a header that
  also has a `flex: 1` title sibling — the title may be claiming space
  the actions container should have kept.
- Possibly `min-width: 0` (the default overflow-shrink behavior)
  applies at a different level than expected, or the negative margins
  used for the "flush to edge" bleed effect are interacting with the
  width calculation (negative margin computed before vs. after
  content-based sizing).

## Files involved

- **CSS:** [app/static/css/custom_css.css](app/static/css/custom_css.css)
  — `.card-header-actions` rule (currently ~line 164):

  ```css
  .card-header-actions {
    display: flex;
    align-self: stretch;
    flex-shrink: 0;
    margin: -0.7rem -1rem -0.7rem 0;
  }

  .card-header-actions .button {
    align-self: stretch;
    height: auto;
    aspect-ratio: 1 / 1;
    border-radius: 0;
    border: none;
    border-left: 1px solid var(--bulma-border-weak);
    white-space: nowrap;
  }
  ```

  Also relevant: the card chamfer rule a bit further down in the same
  file (`@supports (corner-shape: bevel) { .card, .ks-demo-box { ... } }`,
  ~line 355) which is what turns any accidental overflow at a card's
  literal top-right pixel into a diagonal clip — worth revisiting once
  the width overflow itself is fixed, in case the chamfer still shaves
  the button's outer corner and needs its own explicit
  `border-radius: 0 var(--app-chamfer) 0 0` to look intentional.

- **Template:** [app/public_app/templates/kitchen_sink/index.html](app/public_app/templates/kitchen_sink/index.html)
  — "Card Layouts" section, first card ("Basic editable content"),
  currently around line 917:

  ```html
  <div class="card-header" style="gap: 0.5rem;">
    <div class="card-header-title" style="flex: 1;">Basic editable content</div>
    <span class="tag is-success is-light">Active</span>
    <div class="card-header-actions">
      <a class="button is-light" title="View" aria-label="View">
        <span class="icon"><span class="material-icons" aria-hidden="true">visibility</span></span>
      </a>
      <button type="button" class="button is-info is-light" title="Edit" aria-label="Edit">
        <span class="icon"><span class="material-icons" aria-hidden="true">edit</span></span>
      </button>
    </div>
  </div>
  ```

## Suggested next steps

1. Give `.card-header-actions` an explicit `width: max-content;` (or
   `flex-basis: max-content` alongside `flex-shrink: 0`) instead of
   relying on default flex sizing, and re-measure.
2. If that doesn't resolve it, drop `aspect-ratio` on the buttons and
   size them explicitly (`width`/`height` both set to a value read
   from the header's own height via a CSS custom property, or just a
   fixed `2.5rem` square) rather than deriving width from height —
   simpler and removes the sizing-loop suspect entirely.
3. Re-verify with Playwright bounding boxes (not just a screenshot)
   that `.card-header-actions .button:last-child`'s `right` no longer
   exceeds the `.card`'s `right`.
4. Once width is fixed, re-check whether the card's 20px chamfer still
   visibly clips the Edit icon's outer corner, and decide whether to
   add a matching `border-radius` on that button so the cut reads as
   intentional (consistent with how footer buttons already look) or to
   inset the flush margin by `--app-chamfer` so it clears the corner
   entirely.
