---
type: "UX Guide"
title: "File upload"
description: "The <file-upload> web component — a reusable Bulma file field with filename display and multi-file support. Source: app/static/web_components/file_upload.js."
tags: [ux-ui, ux-guide]
context_tier: 2
---

# File upload

`<file-upload>` is a custom element that renders a Bulma `.file has-name` field,
wires the "selected filename" display that Bulma leaves unimplemented, and
supports selecting multiple files. **Use it anywhere the app takes a file upload**
instead of hand-writing the `.file` markup and an inline `onchange` handler.

Source: `app/static/web_components/file_upload.js`.

---

## Usage

Register the script once per page (or in a shared base), then drop the tag inside
a multipart form:

```html
{% load static %}

<form method="post" enctype="multipart/form-data">{% csrf_token %}
  <file-upload name="image" accept="image/*" multiple label="Choose image(s)…"></file-upload>
  <button class="button is-small is-link" type="submit">Upload</button>
</form>

{% block body_scripts %}
<script defer src="{% static 'web_components/file_upload.js' %}"></script>
{% endblock %}
```

### Attributes

| Attribute | Default | Purpose |
| :--- | :--- | :--- |
| `name` | `file` | Form field name. Read server-side with `request.FILES.getlist(name)`. |
| `accept` | *(none)* | Standard `accept` filter passed to the OS picker (e.g. `image/*`, `.pdf`). |
| `multiple` | *(absent)* | Presence allows selecting more than one file. |
| `label` | `Choose file…` | Text shown on the file CTA button. |
| `size` | `is-small` | Bulma file-field size class (`is-small`, `""`, `is-medium`, `is-large`). |
| `empty-text` | `No file selected` | Text shown when nothing is selected. |

### Filename display

The component updates the `.file-name` span on every change:

- **0 files** → `empty-text` ("No file selected")
- **1 file** → that file's name
- **N files** → `"N files selected"`

---

## Why a custom element

- **Self-upgrading.** The browser runs `connectedCallback` whenever the element
  enters the DOM, including after an HTMX swap — no `htmx:afterSwap` re-init and no
  double-bind guards on consumer pages. (Honours the F5 / HTMX rule.)
- **Native form participation.** The real `<input type="file">` is rendered into
  the **light DOM**, so it submits with the enclosing `<form>` exactly like a
  hand-written field. There is no `ElementInternals` / `setFormValue` indirection —
  multi-file `FileList`s reach the server unchanged via `request.FILES.getlist()`.
- **One place for the chrome.** The Bulma `.file has-name` markup and the
  filename logic live in the component, not copy-pasted into every template.
- **Built-in guardrail.** On connect the component checks its enclosing form and
  logs a console warning if `enctype="multipart/form-data"` is missing — the single
  most common reason a file upload silently sends nothing.

---

## Server contract

- **Multipart form only.** The `<form>` **must** carry
  `enctype="multipart/form-data"`, or the browser sends no file bytes and
  `request.FILES` is empty. The component can render inside any form but cannot set
  this for you — it belongs on the `<form>`. (The component warns in the console if
  it is missing.)
- **Read with `getlist`.** Use `request.FILES.getlist(name)` even for a single
  file — `request.FILES[name]` returns only the last file when several are sent.
- **Validate server-side.** `accept` only hints the OS picker; it is not
  enforcement. Gate real uploads on the server (e.g. `File.is_allowed_extension`).

---

## Rules

- **Always inside a multipart `<form>`.** Not a standalone control.
- **Set `name=`** to match what the view reads.
- **One field per logical upload slot.** Two distinct uploads → two elements with
  distinct `name=` attributes.
- **Do not style the internals from page CSS.** The markup is Bulma's standard
  `.file` structure; restyle via the `size` attribute or extend the component, not
  ad-hoc selectors.
- **Register the script once.** A second `<script>` for the same component is
  harmless (guarded by `customElements.get`) but unnecessary.

---

## Common pitfalls

- **Form missing `enctype`.** Nothing uploads; check the console warning.
- **Reading `request.FILES[name]` for a multi-file field.** Only the last file
  arrives — use `getlist`.
- **Expecting `accept` to enforce type.** It filters the picker only; enforce on
  the server.
- **Forgetting `{% load static %}`** on a template that adds the `<script>` tag in
  its own block.
