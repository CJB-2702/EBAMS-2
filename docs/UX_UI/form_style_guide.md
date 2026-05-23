# Form & action layout style guide

How **Create**, **Edit**, **Delete**, **Cancel**, and other actions are positioned on cards, forms, and inline controls. The geometry is the same everywhere so users build muscle memory: *primary on the bottom-right, dangerous things small and far from the primary*.

For the master button table see [common_buttons.md](common_buttons.md). For verbatim card-footer markup see [Examples/card_footer_markup.md](Examples/card_footer_markup.md).

---

## Core rule

> **All Create/Edit/Delete/Cancel actions live at the bottom of their parent container.**

The "parent container" is whichever of these is closest:
1. A `.card` (preferred) → actions go in `.card-footer`.
2. A `<form>` directly inside `.card-content` → actions go in a footer row at the bottom of the form.
3. An inline form-addon (single field) → submit is flush against the field (see [Inline single-field forms](#inline-single-field-forms)).

Never float buttons outside the card. Never anchor buttons to the viewport.

---

## Geometry

Inside the footer row:

| Slot | Width | Contents |
| :--- | :--- | :--- |
| **Bottom-right (primary)** | **50%** of the footer row | The single primary action (Save / Create / Submit / Apply). Full-width within its 50% column. |
| **Bottom-left (secondary)** | Remaining 50%, **inline** | Cancel, Reset, and (where applicable) Delete. Smaller buttons, left-aligned, inline with each other. |

### Why 50/50

- Half the row reserves visual weight for the primary action so it is the obvious target.
- The other half packs as many secondary actions inline as you need without the primary moving.
- It is the same geometry on a 320px phone and a 1920px desktop — the columns shrink proportionally.

The project provides three CSS classes to keep markup clean:

| Class | Applied to | Effect |
| :--- | :--- | :--- |
| `custom-card-footer` | `<footer class="card-footer">` | Grid layout with `grid-template-columns: 1fr 1fr`, `gap: 0.5rem`, `align-items: stretch` |
| `card-footer-secondaries` | A `<div>` wrapping secondary buttons | Groups Cancel / Reset / Delete on the left with flex layout. Use an empty div if there are no secondary buttons. |
| `card-footer-primary` | The primary button | Stretches to full height of the footer. Never add `is-small` to the primary button. |

---

## Delete protocol

Delete is always a **secondary** action — it never sits in the primary slot, and it is **visually narrower** than the other secondaries.

| Property | Value |
| :--- | :--- |
| Slot | Bottom-left, inline with Cancel/Reset |
| Style | `is-small is-danger is-light` (light red, not solid red) |
| Width | Capped via `style="max-width: 6rem;"` or `is-small` only — explicitly **less wide** than Cancel |
| Confirmation | Required. Use a native `<dialog>` modal (see [modals.md](modals.md)) for non-trivial deletes; a `confirm()` is acceptable for low-stakes removals. |
| Position relative to Cancel | **Right of Cancel/Reset** so the user's pointer travels through the safer buttons first |

Never make Delete the primary action of an edit form. If a screen exists *only* to delete a thing, the primary action on that screen is the deletion — but that is a dedicated screen, not the edit form.

### Why Delete is small

The button's visual weight should match the **frequency** of the action, not its consequence. Edit and Save happen all day; deletes are rare. A small button keeps it discoverable but not inviting.

---

## Inline single-field forms

When a form has **exactly one** field (renaming a domain, editing a tag label, changing a display name in place), the canonical 50/50 footer is overkill. Use Bulma's `field has-addons` pattern instead — submit is flush with the input on its right.

Rules for inline forms:

- **No Cancel button.** The user cancels by navigating away or pressing Escape.
- **No Delete in an inline form.** Delete affects the row/parent, not the field — put Delete on the parent's footer.
- **Use `is-expanded`** on the input's control so the field grows and the button stays its natural width.
- **Submit on Enter** must work — that is the entire reason this pattern exists.

### When to graduate from inline to a full form

Switch to the full card-footer pattern as soon as the form gains any of:
- A second field.
- A required confirmation step.
- A Cancel that does anything more than "navigate away".
- Multiple submit actions.

---

## Reset, Clear, and other tertiary controls

Tertiary controls (Reset, Clear all, Restore defaults) live **left of Cancel** in the secondary slot, sized `is-small is-light`. They never appear without a Cancel — if there is nothing to cancel back to, there is nothing to reset to either.

If the form has a **Clear** that empties draft state in `request.session`, prefer wiring it as a regular form submit with `name="action" value="clear"` rather than client-side JS — keeps the F5 rule intact.

---

## Common mistakes

- **Delete in the primary slot.** It is destructive *and* rare — never the dominant action.
- **Solid `is-danger` Delete.** The light variant signals "secondary destructive" and matches Cancel's visual weight.
- **Cancel on the right of Save.** Breaks left-to-right reading: secondary should always be reached *before* primary.
- **Stretching Delete to match Cancel.** Delete must be visibly the **narrowest** button on the row.
- **Adding a duplicate primary submit inside `.card-content`.** The primary lives in the footer; one form, one primary submit.
- **Inline form with a Cancel button.** If you need Cancel, you have outgrown the inline pattern.
- **Per-field "Save" buttons inside a multi-field form.** One submit at the bottom commits the whole form.
