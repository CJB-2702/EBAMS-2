---
type: "UX Example"
title: "File upload field markup"
description: "Canonical Bulma file-input markup with the filename-display handler and multi-file support."
tags: [ux-ui, ux-example, examples]
context_tier: 3
---

# File upload field markup

Canonical markup for a Bulma `has-name` file input. Two things are easy to get
wrong and both break silently:

1. The `<form>` **must** carry `enctype="multipart/form-data"`, or the browser
   sends no file bytes and `request.FILES` is empty on the server.
2. The `.file-name` span is purely presentational — Bulma ships no JS, so it
   stays on "No file selected" unless an `onchange` handler updates it.

```html
<form method="post" enctype="multipart/form-data">{% csrf_token %}
  <div class="file is-small has-name mb-3">
    <label class="file-label">
      <input class="file-input" type="file" name="image" accept="image/*" multiple
             onchange="this.closest('.file').querySelector('.file-name').textContent = this.files.length ? (this.files.length === 1 ? this.files[0].name : this.files.length + ' files selected') : 'No file selected';">
      <span class="file-cta">
        <span class="file-icon"><span class="material-icons" aria-hidden="true">attach_file</span></span>
        <span class="file-label">Choose image(s)…</span>
      </span>
      <span class="file-name">No file selected</span>
    </label>
  </div>
  <button class="button is-small is-link" type="submit">
    <span class="icon"><span class="material-icons" aria-hidden="true">upload</span></span>
    <span>Upload</span>
  </button>
</form>
```

## Notes

- Drop `multiple` from the `<input>` for a single-file field. When present, read
  the files server-side with `request.FILES.getlist("image")` (not
  `request.FILES["image"]`, which returns only the last file).
- The `onchange` handler walks up to the enclosing `.file` and updates its
  `.file-name` span: the filename for one file, `"N files selected"` for many,
  and back to `"No file selected"` when the selection is cleared.
- `accept="image/*"` filters the OS file picker to images only; adjust or remove
  for other upload types.
- After a successful POST the page redirects (post/redirect/get), so the form
  resets to "No file selected" on its own — that reset is expected, not a bug.
