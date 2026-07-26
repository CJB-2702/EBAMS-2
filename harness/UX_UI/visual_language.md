---
type: "UX Guide"
title: "Visual language and tokens"
description: "No pill buttons."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# Visual language and tokens

The chrome of the application is Bulma 1.0.x, with a thin project CSS layer that:

- Sets all Bulma radius variables to `0` so corners stay sharp.
- Declares `color-scheme: light dark` and uses Bulma scheme variables (`--bulma-scheme-main`, `--bulma-scheme-main-bis`, `--bulma-border`, `--bulma-text`) so the app flips with OS preference.
- Adds named patterns (page hero, card footer, dual listbox) without forking Bulma.

## Tokens

| Concern | Token / approach |
| :--- | :--- |
| Radius | `--bulma-radius: 0`, `--bulma-box-radius: 0`, `--bulma-card-radius: 0`, etc. Set on `:root`. |
| Color scheme | `color-scheme: light dark` on `:root`; all greys come from Bulma scheme variables, never hardcoded `#fafafa` / `#ededed`. |
| Spacing | Bulma's default Bulma scale. The project CSS adds `--app-section-gap`, `--app-card-gap` for portal sections; do not invent new pixel constants per page. |
| Borders | `1px solid var(--bulma-border-weak)` for default; `1px solid var(--bulma-border)` for separators that should remain visible in either theme. Left accents (page hero, active nav) are `3px` in the primary colour. |
| Typography | Bulma defaults. Section labels are `0.6–0.65rem` uppercase, letter-spaced, in `var(--bulma-text-weak)`. Page titles are `1.85rem` inside a hero, `1.25rem` in standard headers. |

## Square or chamfered — never rounded

No pill buttons. No rounded cards. No "softened" inputs. The radius pinning is in `:root` so any new Bulma component picks up the rule automatically. If a third-party widget arrives with its own radius, set it to `0` in the project CSS — do not request an exception.

Corners are either perfectly square, or cut at a 45° angle (a chamfer) on the project's main surface containers (`.card`, `.notification`, `.page-hero`, `.modal-styled`). See [components/chamfers.md](components/chamfers.md) for how the chamfer layer works and how to add or remove it from an element. A chamfer is not a rounded corner — do not substitute `border-radius` alone for it.

The chamfer marks a **container**, not its contents: a card that composes a section keeps the cut, while small repeated items stacked inside it (comment rows, revision entries) opt out with `sharp-corners` so a 20px cut never nests inside another one.

## Cards as the default container

- **Every self-contained content block — portals, primary forms, list items, thread/comment cards — wraps in `.card`.** Put copy and fields in `.card-content`. Put actions in `.card-footer` (see [form_style_guide.md](form_style_guide.md)).
- **`.card`, `.card-header`, and `.card-content` are overridden project-wide** in `custom_css.css` to look different from stock Bulma: a flat `1px solid var(--bulma-border-weak)` border instead of Bulma's drop shadow, a `border-bottom` divider under `.card-header` instead of its default box-shadow, tighter header/content padding, and `font-weight: 600` (not Bulma's bold) on the header. This is one global override, not a per-page or per-app choice — never re-add Bulma's stock shadow/padding locally to "restore the default look."
- **Card footer geometry** is documented in [form_style_guide.md](form_style_guide.md). Do not invent ad-hoc footer rows.
- **Card overflow:** `overflow: hidden` on the card root clips content that overflows its (now-zero-radius) box. Dark mode's Bulma vendor CSS also sets `border-*-radius` directly on `.card-header:first-child` / `.card-content` / `.card-footer:last-child` from a non-zero `--bulma-card-radius`, which is its own corner paint rather than overflow — `custom_css.css` zeroes those selectors literally so no theme reintroduces a rounded corner.

There used to be a second, hand-rolled card component (`.pc`/`.pc-header`/`.pc-body`) duplicated inline across several apps' base templates, doing the same job as `.card` with slightly different styling. It has been folded into `.card` — if you see `.pc` referenced anywhere (old docs, old branches), treat it as the same thing `.card` now does.

## Material Icons

Icons come from vendored Material Icons (`static/fonts/material-icons/`). Use the `<span class="icon"><span class="material-icons" aria-hidden="true">icon_name</span></span>` shape. Icons paired with text labels follow the master button table in [components/common_buttons.md](components/common_buttons.md).

## Dark mode

The OS preference is the source of truth. Tests should pass with `prefers-color-scheme: dark` set. Pages that hardcode light backgrounds (`background: #fafafa`, `has-background-light` outside theme-aware contexts) are bugs, not stylistic choices.

## Common mistakes

- **Hardcoded greys** that don't flip in dark mode.
- **Reintroducing rounded corners** to "soften" a card or a button — use a chamfer (see [components/chamfers.md](components/chamfers.md)) if a cut corner is wanted, never `border-radius` alone.
- **Mixing inline styles with the project CSS layer** — keep theme tokens in CSS, not in templates.
- **Per-page custom colour scales** — extend the master button table in [components/common_buttons.md](components/common_buttons.md) before adding a one-off colour.
