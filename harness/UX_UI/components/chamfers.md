---
type: "UX Guide"
title: "Chamfered Corners"
description: "How the app-wide 45° corner bevel works, and how to add or remove it from an element."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Chamfered corners

The project's containers use a **45° cut corner** (a chamfer/bevel), not a rounded corner. This is deliberate: corners are either perfectly square or cut at an angle — never curved. See [visual_language.md](../visual_language.md) for how this fits the rest of the visual language.

All of it lives in one place: `app/static/css/custom_css.css`, in the block headed `── Chamfered containers ──` (around line 323), plus the escape hatch at the end of the file.

---

## How it works

Chamfering uses the CSS Borders L4 `corner-shape: bevel` property paired with `border-radius`, **not** `clip-path`:

```css
.card {
  corner-shape: bevel;
  border-radius: var(--app-chamfer);
}
```

`corner-shape: bevel` tells the browser to draw the existing border/background along a straight diagonal instead of a curve at the radius distance. `clip-path` was rejected for this because it crops the border and shadow off the diagonal rather than drawing along it — the container's outline would look cut off rather than genuinely cornered.

The whole layer is gated behind a feature query:

```css
@supports (corner-shape: bevel) {
  ...
}
```

Browsers without `corner-shape` support simply never apply the `border-radius`, so they fall back to the project's default square corner. They must **never** fall back to a rounded corner — that would violate the "square or chamfered, never curved" rule the whole design language is built on. This is why the bevel and the radius are always declared together, inside the `@supports` gate, and never as a bare `border-radius` outside it.

### The size token

```css
:root {
  --app-chamfer: 20px;
}
```

One token controls the standard cut size for every chamfered surface at once. Don't hardcode `20px` in a new rule — reference `var(--app-chamfer)`.

---

## What's chamfered today

| Selector | Corners cut | Size |
| :--- | :--- | :--- |
| `.card`, `.ks-demo-box` | all four | `var(--app-chamfer)` (20px) |
| `.notification` | all four | `10px` (smaller so short inline messages don't read as octagons) |
| `.page-hero` | right two only (TL/BL stay square) | `var(--app-chamfer)` |
| `.modal-styled` | all four | `var(--app-chamfer)` |

`<dialog class="card modal-styled">` is both a card and a modal, so its chamfer rule has to live **after** `.modal-styled`'s own `border-radius: 0 !important` reset earlier in the file — same specificity and both `!important`, so source order decides. Keep that ordering if you touch either rule.

### What's deliberately square

| Element | Template | Why |
| :--- | :--- | :--- |
| Comment row | `events/fragments/comment_row.html` | Repeated content inside an already-chamfered thread card |
| Comment revision entry | `events/comment/history.html` | Same — an individual comment body |

Both carry `sharp-corners`. The rule of thumb: **the chamfer marks a container, not its contents.** A card that composes a section keeps the bevel; small repeated bubbles stacked inside it go square, so a 20px cut doesn't nest inside another 20px cut. The Comments card and the Add/Edit Comment card (`<add-comment>`) are containers and stay chamfered; the rows between them are contents and are square.

Because every app's activity thread renders through those two events templates (see [comments](../../DOMAIN/events/)), the class lives there and propagates — never re-add it per calling app.

---

## Adding a chamfer to a new element

1. Add a rule inside the existing `@supports (corner-shape: bevel) { ... }` block in `custom_css.css` (near the other chamfered selectors, line ~334):

   ```css
   @supports (corner-shape: bevel) {
     .your-selector {
       corner-shape: bevel;
       border-radius: var(--app-chamfer);
     }
   }
   ```

2. Use `border-radius: <TL> <TR> <BR> <BL>` shorthand to cut only some corners, the way `.page-hero` does:

   ```css
   .your-selector {
     corner-shape: bevel;
     border-radius: 0 var(--app-chamfer) var(--app-chamfer) 0; /* right two only */
   }
   ```

3. If the element already has an unrelated `border-radius: 0` rule elsewhere in the file (sharp-corner reset, dark-mode override, etc.) with equal specificity, your chamfer rule must come **after** it in source order or it will lose the cascade tie — see the `.modal-styled` case above.

4. Pick a cut size: use `var(--app-chamfer)` for a standard surface, or a smaller literal (see `.notification`'s `10px`) for compact/inline elements where the full 20px cut would look disproportionate.

---

## Removing a chamfer from one element

Add the `sharp-corners` utility class alongside the element's own classes:

```html
<div class="card sharp-corners"> … </div>
```

`.sharp-corners` is `border-radius: 0 !important`, kept last in `custom_css.css` so it wins over every chamfer rule above it — including the `!important` modal bevel. Use this for one-off exceptions; don't fork the base selector's rule to exclude a class.

To remove chamfering from a selector **app-wide**, delete (or comment out) its rule inside the `@supports (corner-shape: bevel)` block rather than sprinkling `sharp-corners` across every template that uses it.

---

## Common mistakes

- **Using `clip-path` instead of `corner-shape: bevel`** — crops the border/shadow off the diagonal instead of drawing along it.
- **Hardcoding a pixel value** instead of `var(--app-chamfer)` for a standard-size surface.
- **Declaring `border-radius` outside the `@supports` gate** — unsupported browsers would get a rounded corner instead of the intended square fallback.
- **Rounded corners as a "softer" alternative** — not a valid chamfer substitute; see [visual_language.md](../visual_language.md).
