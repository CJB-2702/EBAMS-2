// App-specific web component (events app): the "Add Comment" card — header,
// comment field, an optional preview list of files chosen for upload (styled
// like <file-browser>'s tiles, see file_browser.js / custom_css.css), and a
// footer with Clear / Attach Files on the left and Add on the right.
//
// Also doubles as the inline comment-EDIT card (mode="edit"): same chrome,
// but the header reads "Editing" with a Cancel button (HTMX back to the
// read-only row), the footer's Clear button re-fetches the edit endpoint
// itself instead of resetting client-side, the submit button reads "Save",
// and existing (already-saved) attachments render in the same file-tile grid
// as newly-staged ones, each with a remove/restore toggle that adds/removes a
// hidden `remove_attachments` input rather than deleting anything itself —
// see events/comment/fragments/comment_edit_form.html and
// events/presentation_layer/entrypoints/comments.py::comment_edit.
//
// Like <file-upload> (file_upload.js), this renders its real <textarea> and
// <input type="file"> into the LIGHT DOM so they submit natively with the
// enclosing <form> via request.POST["content"] / request.FILES.getlist("files") —
// no shadow root, no custom submit handling. This component only owns the
// chrome and the pre-submit file preview; the actual POST, HTMX swap, and
// server-side validation/guards are unchanged (see events/comment_handler.py
// and events/presentation_layer/entrypoints/comments.py::comment_add/comment_edit).
//
// Usage — add (inside a <form method=post enctype=multipart/form-data ...>):
//   <add-comment placeholder="Write a comment…" error="{{ comment_error }}"></add-comment>
//
// Usage — edit:
//   <add-comment mode="edit" content="{{ comment.content }}" depth="{{ row_depth }}"
//                cancel-url="{% url 'comment_view_row' ... %}"
//                reload-url="{% url 'comment_edit' ... %}?format=htmx-comment-row"
//                existing-attachments='{{ existing_attachments_json }}'
//                error="{{ errors|join:' ' }}"></add-comment>
//
// Cancel/Clear target "closest [id^='comment-row-']" rather than an exact id —
// the enclosing comment row/edit-form wrapper — so this still resolves to the
// right instance even when the same comment_hash's id is duplicated elsewhere
// on the page (e.g. the kitchen sink demos one sample comment in several
// sections at once).

class AddComment extends HTMLElement {
  connectedCallback() {
    if (this._built) return;
    this._built = true;

    const isEdit = this.getAttribute("mode") === "edit";
    const placeholder = this.getAttribute("placeholder") || "Write a comment…";
    const error = this.getAttribute("error") || "";
    const content = this.getAttribute("content") || "";
    const depth = this.getAttribute("depth") || "depth-2";
    const cancelUrl = this.getAttribute("cancel-url") || "";
    const reloadUrl = this.getAttribute("reload-url") || "";
    const rowTarget = "closest [id^='comment-row-']";
    this._files = [];
    this._removedExisting = new Set();
    try {
      this._existing = JSON.parse(this.getAttribute("existing-attachments") || "[]");
    } catch (e) {
      this._existing = [];
    }

    const headerIcon = isEdit ? "edit" : "add_comment";
    const headerTitle = isEdit ? "Editing" : "Add Comment";
    const submitIcon = isEdit ? "save" : "send";
    const submitLabel = isEdit ? "Save" : "Add";
    const margin = isEdit ? "mb-2" : "mt-2";

    // Cancel/Clear/Attach Files sit on the card's own background — is-light
    // reads as "invisible" once that background is already a depth-2/3 gray,
    // so step one depth level past whatever this card is sitting at instead.
    const depthNum = parseInt((depth.match(/\d+/) || ["2"])[0], 10);
    const buttonDepth = `depth-${Math.min(depthNum + 1, 4)}`;

    this.innerHTML = `
      <div class="card ${this._attr(depth)} ${margin}">
        <div class="card-header">
          <div class="card-header-title">
            <span class="icon"><span class="material-icons is-size-7" aria-hidden="true">${headerIcon}</span></span>
            ${headerTitle}
          </div>
          ${isEdit ? `
          <button type="button" class="button is-small ${buttonDepth} ac-cancel" title="Cancel">
            <span class="icon"><span class="material-icons is-size-7" aria-hidden="true">close</span></span>
            <span>Cancel</span>
          </button>` : ``}
        </div>
        <div class="card-content">
          <p class="help is-danger is-size-7 ac-error"${error ? "" : " hidden"}>${this._esc(error)}</p>
          <div class="field">
            <div class="control">
              <textarea class="textarea is-small ac-content" name="content" rows="2"
                        placeholder="${this._attr(placeholder)}" required>${this._esc(content)}</textarea>
            </div>
          </div>
          <div class="ac-file-list"></div>
          <input type="file" name="files" multiple hidden class="ac-file-input">
          <div class="ac-remove-inputs"></div>
        </div>
        <footer class="card-footer custom-card-footer">
          <div class="card-footer-secondaries">
            <button type="button" class="button is-small is-link is-light ac-clear">Clear</button>
            <button type="button" class="button is-small is-link is-light ac-attach">
              <span class="icon"><span class="material-icons" aria-hidden="true">attach_file</span></span>
              <span>Attach Files</span>
            </button>
          </div>
          <button type="submit" class="button is-primary card-footer-primary">
            <span class="icon"><span class="material-icons" aria-hidden="true">${submitIcon}</span></span>
            <span>${submitLabel}</span>
          </button>
        </footer>
      </div>
    `;

    this.textarea = this.querySelector(".ac-content");
    this.input = this.querySelector(".ac-file-input");
    this.listEl = this.querySelector(".ac-file-list");
    this.removeInputsEl = this.querySelector(".ac-remove-inputs");

    this.querySelector(".ac-attach").addEventListener("click", () => this.input.click());
    this.input.addEventListener("change", () => this._onFilesPicked());

    const clearBtn = this.querySelector(".ac-clear");
    if (isEdit && reloadUrl) {
      // "Clear" in edit mode discards in-progress changes by re-fetching the
      // same endpoint that loaded this form, rather than resetting fields
      // client-side — declarative HTMX attrs need an explicit process() call
      // since they're added after this element's own htmx:load pass.
      clearBtn.setAttribute("hx-get", reloadUrl);
      clearBtn.setAttribute("hx-target", rowTarget);
      clearBtn.setAttribute("hx-swap", "outerHTML");
    } else {
      clearBtn.addEventListener("click", () => this._clear());
    }

    if (isEdit) {
      const cancelBtn = this.querySelector(".ac-cancel");
      cancelBtn.setAttribute("hx-get", cancelUrl);
      cancelBtn.setAttribute("hx-target", rowTarget);
      cancelBtn.setAttribute("hx-swap", "outerHTML");
    }

    if (isEdit && window.htmx) {
      window.htmx.process(this);
    }

    this._renderFileList();

    // Developer guardrail, same rationale as <file-upload>: files silently
    // never reach the server if the form lacks multipart encoding.
    const form = this.input.form;
    if (form && form.enctype !== "multipart/form-data") {
      console.warn(
        "<add-comment>: enclosing <form> is missing enctype=\"multipart/form-data\"; " +
          "selected files will not be uploaded.",
        form
      );
    }
  }

  // --- file selection ------------------------------------------------------

  _onFilesPicked() {
    // A fresh pick from the OS dialog REPLACES input.files rather than adding
    // to it, so accumulate into our own array across multiple "Attach Files"
    // clicks, then rebuild input.files from the full set via DataTransfer.
    Array.from(this.input.files).forEach((f) => this._files.push(f));
    this._syncInput();
    this._renderFileList();
  }

  _removeFile(idx) {
    this._files.splice(idx, 1);
    this._syncInput();
    this._renderFileList();
  }

  _toggleExisting(id) {
    if (this._removedExisting.has(id)) this._removedExisting.delete(id);
    else this._removedExisting.add(id);
    this._renderFileList();
  }

  _syncInput() {
    const dt = new DataTransfer();
    this._files.forEach((f) => dt.items.add(f));
    this.input.files = dt.files;
  }

  _clear() {
    this.textarea.value = "";
    this._files = [];
    this._syncInput();
    this._renderFileList();
  }

  // --- rendering ------------------------------------------------------------

  _renderFileList() {
    this.listEl.innerHTML = "";
    this.removeInputsEl.innerHTML = "";
    if (this._existing.length === 0 && this._files.length === 0) return;

    const grid = document.createElement("div");
    grid.className = "fb-grid mb-2";

    this._existing.forEach((att) => {
      const removed = this._removedExisting.has(att.id);
      const tile = document.createElement("div");
      tile.className = "fb-tile" + (removed ? " ac-removed" : "");
      tile.innerHTML = `
        <span class="fb-tile-link">
          <span class="fb-thumb">
            <span class="material-icons" aria-hidden="true">${att.is_image ? "image" : "description"}</span>
          </span>
          <span class="fb-meta">
            <span class="fb-name">${this._esc(att.name)}</span>
            <span class="fb-sub">${this._fmtSize(att.size)}</span>
          </span>
        </span>
        <span class="fb-tile-actions">
          <button type="button" class="button is-small ac-toggle-existing" title="${removed ? "Restore" : "Remove"}">
            <span class="material-icons" aria-hidden="true">${removed ? "undo" : "close"}</span>
          </button>
        </span>`;
      tile.querySelector(".ac-toggle-existing").addEventListener("click", () => this._toggleExisting(att.id));
      grid.appendChild(tile);

      if (removed) {
        const hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = "remove_attachments";
        hidden.value = att.id;
        this.removeInputsEl.appendChild(hidden);
      }
    });

    this._files.forEach((file, idx) => {
      const isImage = file.type.startsWith("image/");
      const tile = document.createElement("div");
      tile.className = "fb-tile";
      tile.innerHTML = `
        <span class="fb-tile-link">
          <span class="fb-thumb">
            ${isImage ? `<img alt="">` : `<span class="material-icons" aria-hidden="true">description</span>`}
          </span>
          <span class="fb-meta">
            <span class="fb-name">${this._esc(file.name)}</span>
            <span class="fb-sub">${this._fmtSize(file.size)}</span>
          </span>
        </span>
        <span class="fb-tile-actions">
          <button type="button" class="button is-small ac-remove-file" title="Remove">
            <span class="material-icons" aria-hidden="true">close</span>
          </button>
        </span>`;
      if (isImage) {
        tile.querySelector("img").src = URL.createObjectURL(file);
      }
      tile.querySelector(".ac-remove-file").addEventListener("click", () => this._removeFile(idx));
      grid.appendChild(tile);
    });

    this.listEl.appendChild(grid);
  }

  // --- helpers ---------------------------------------------------------------

  _fmtSize(bytes) {
    if (!bytes) return "—";
    const units = ["B", "KB", "MB", "GB"];
    let n = bytes, u = 0;
    while (n >= 1024 && u < units.length - 1) { n /= 1024; u++; }
    return `${n < 10 && u > 0 ? n.toFixed(1) : Math.round(n)} ${units[u]}`;
  }

  _esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  _attr(s) {
    return this._esc(s).replace(/"/g, "&quot;");
  }
}

if (!customElements.get("add-comment")) {
  customElements.define("add-comment", AddComment);
}
