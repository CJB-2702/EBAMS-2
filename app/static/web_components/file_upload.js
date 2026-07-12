// DELIBERATE ANTI PATTERN: THIS WEBCOMPONENT MANUALLY ADDS BULMA COMPONENTS AND UI ELEMENTS
// (same rationale as search_dropdown.js) — a file field's chrome and interaction are
// uniform and simple enough that reproducing the Bulma `.file has-name` markup inside the
// component is easier than any alternative. The real <input type="file"> is rendered into
// the LIGHT DOM (not a shadow root) on purpose, so it participates natively in the enclosing
// <form> and submits with request.FILES.getlist(name) exactly like a hand-written field.

class FileUpload extends HTMLElement {
  connectedCallback() {
    // connectedCallback can fire more than once (e.g. HTMX moving the node). Only build once.
    if (this._built) {
      return;
    }
    this._built = true;

    const name = this.getAttribute("name") || "file";
    const accept = this.getAttribute("accept");
    const multiple = this.hasAttribute("multiple");
    const label = this.getAttribute("label") || "Choose file…";
    const size = this.getAttribute("size") || "is-small"; // is-small | "" | is-medium | is-large
    const emptyText = this.getAttribute("empty-text") || "No file selected";
    // fullwidth: the "choose" CTA spans the whole card width instead of hugging its label.
    const fullwidth = this.hasAttribute("fullwidth");

    this.innerHTML = `
      <div class="file ${size}${fullwidth ? " is-fullwidth" : ""} mb-2">
        <label class="file-label">
          <input class="file-input" type="file" name="${name}"${accept ? ` accept="${accept}"` : ""}${multiple ? " multiple" : ""}>
          <span class="file-cta">
            <span class="file-icon"><span class="material-icons" aria-hidden="true">attach_file</span></span>
            <span class="file-label">${label}</span>
          </span>
        </label>
      </div>
      <ul class="file-selected-list mb-3"></ul>
    `;

    this.input = this.querySelector("input.file-input");
    this.listEl = this.querySelector(".file-selected-list");
    this._emptyText = emptyText;
    this._renderName();

    this.input.addEventListener("change", () => this._renderName());

    // Developer guardrail: files silently never reach the server if the form lacks
    // the multipart encoding. Warn loudly in the console rather than failing quietly.
    const form = this.input.form;
    if (form && form.enctype !== "multipart/form-data") {
      console.warn(
        "<file-upload>: enclosing <form> is missing enctype=\"multipart/form-data\"; " +
          "selected files will not be uploaded.",
        form
      );
    }
  }

  _renderName() {
    const files = this.input.files;
    this.listEl.innerHTML = "";
    if (!files || files.length === 0) {
      const li = document.createElement("li");
      li.className = "is-size-7 has-text-grey";
      li.textContent = this._emptyText;
      this.listEl.appendChild(li);
      return;
    }
    Array.from(files).forEach((file) => {
      const li = document.createElement("li");
      li.className =
        "is-flex is-align-items-center is-size-7 py-1";
      const icon = document.createElement("span");
      icon.className = "icon is-small mr-1 has-text-grey";
      icon.innerHTML =
        '<span class="material-icons" aria-hidden="true" style="font-size:1rem;">insert_drive_file</span>';
      const nameSpan = document.createElement("span");
      nameSpan.className = "is-flex-grow-1";
      // textContent (not innerHTML) — filenames are untrusted and must not be parsed as markup.
      nameSpan.textContent = file.name;
      const sizeSpan = document.createElement("span");
      sizeSpan.className = "has-text-grey ml-2";
      sizeSpan.textContent = this._formatSize(file.size);
      li.append(icon, nameSpan, sizeSpan);
      this.listEl.appendChild(li);
    });
  }

  _formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // Convenience passthroughs so page scripts can inspect the field without reaching into it.
  get files() {
    return this.input ? this.input.files : null;
  }

  get name() {
    return this.getAttribute("name");
  }
}

if (!customElements.get("file-upload")) {
  customElements.define("file-upload", FileUpload);
}
