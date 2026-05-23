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

## Sharp corners — no exceptions

No pill buttons. No rounded cards. No "softened" inputs. The radius pinning is in `:root` so any new Bulma component picks up the rule automatically. If a third-party widget arrives with its own radius, set it to `0` in the project CSS — do not request an exception.

## Cards as the default container

- **Portals and primary forms:** wrap the main content in a `.card`. Put copy and fields in `.card-content`. Put actions in `.card-footer` (see [form_style_guide.md](form_style_guide.md)).
- **Card footer geometry** is documented in [form_style_guide.md](form_style_guide.md). Do not invent ad-hoc footer rows.
- **Card overflow:** `overflow: hidden` on the card root so any rounded-button-corner relic is clipped by the (now-zero) radius regardless of theme.

## Material Icons

Icons come from vendored Material Icons (`static/fonts/material-icons/`). Use the `<span class="icon"><span class="material-icons" aria-hidden="true">icon_name</span></span>` shape. Icons paired with text labels follow the master button table in [common_buttons.md](common_buttons.md).

## Dark mode

The OS preference is the source of truth. Tests should pass with `prefers-color-scheme: dark` set. Pages that hardcode light backgrounds (`background: #fafafa`, `has-background-light` outside theme-aware contexts) are bugs, not stylistic choices.

## Common mistakes

- **Hardcoded greys** that don't flip in dark mode.
- **Reintroducing rounded corners** to "soften" a card or a button.
- **Mixing inline styles with the project CSS layer** — keep theme tokens in CSS, not in templates.
- **Per-page custom colour scales** — extend the master button table in [common_buttons.md](common_buttons.md) before adding a one-off colour.
