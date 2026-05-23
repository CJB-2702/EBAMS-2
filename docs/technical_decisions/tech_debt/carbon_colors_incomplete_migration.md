# Carbon Colors / event detail depth system — incomplete migration

## What this debt is

The event detail page (`http://127.0.0.1:8000/events/<hash>/`) still has unfinished work on the depth/elevation system and card styling. The Carbon-inspired color scheme has been partially applied but the event detail surface was not finished.

## Why deferred

The kitchen-sink session that drove the Carbon migration ran out of time on the events surface. The administration portal and the kitchen sink itself were the focus; the event detail page was left for later.

## What "fixed" looks like

- The event detail page uses the same depth tokens (border colors, shadow tiers) as the rest of the administration portal.
- Card styling on the page matches the canonical patterns in [../../UX_UI/page_structure.md](../../UX_UI/page_structure.md) and [../../UX_UI/visual_language.md](../../UX_UI/visual_language.md).
- Dark-mode behaviour is consistent across the events portal — no hardcoded light backgrounds.
- The page passes a visual review against the kitchen-sink examples.
