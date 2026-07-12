/**
 * <file-browser> — a file-browser web component for an attachment set.
 *
 * Progressive enhancement / F5 rule: the server renders one plain <a> per file
 * as a light-DOM child (with data-* metadata). With JS off those links are the
 * usable fallback. With JS on, the component hides the raw children and paints
 * a toolbar (view toggle, search, type + uploader filters, sort) over a
 * re-rendered Tiles or List view. All filtering/sorting is vanilla JS over the
 * child nodes — these sets are small, so no server round trips are needed.
 *
 * Expected child markup (one per file):
 *   <a class="fb-item" href="/download/..."
 *      data-name="spec.pdf" data-caption="Rev A" data-type="document"
 *      data-icon="image|glyph" data-thumb="/inline/..."  (thumb optional)
 *      data-size="284119" data-date="2026-05-14T09:32:00Z"
 *      data-user="Jane Doe" data-date-display="May 14, 2026" data-id="...">
 *     <span slot="actions"> ...server-rendered per-item actions... </span>
 *   </a>
 *
 * Attributes on the host:
 *   default-view="tiles|list"   initial view (localStorage overrides)
 *   storage-key="..."           localStorage key for the view preference
 */
class FileBrowser extends HTMLElement {
  constructor() {
    super();
    this._items = [];
    this._view = "tiles";
    this._sortKey = "date";
    this._sortDir = "desc";
    this._search = "";
    this._typeFilter = "all";
    this._userFilter = "all";
  }

  connectedCallback() {
    if (this._mounted) return;
    this._mounted = true;

    this._items = this._readItems();
    this._storageKey = this.getAttribute("storage-key") || "file-browser-view";
    this._view = this._loadView();

    this.classList.add("file-browser");
    this._render();
  }

  /**
   * Programmatically switch this browser's view ("tiles" | "list").
   * Used by the page-level "toggle all" control. No-op for unknown values.
   */
  setView(view) {
    if (view !== "tiles" && view !== "list") return;
    if (!this._mounted || view === this._view) return;
    this._view = view;
    this._saveView();
    this._syncToolbarState();
    this._renderBody();
  }

  // --- data ---------------------------------------------------------------

  _readItems() {
    return Array.from(this.querySelectorAll(".fb-item")).map((el) => {
      const actions = el.querySelector('[slot="actions"]');
      return {
        href: el.getAttribute("href") || "#",
        name: el.dataset.name || "",
        caption: el.dataset.caption || "",
        type: el.dataset.type || "document",
        thumb: el.dataset.thumb || "",
        size: parseInt(el.dataset.size || "0", 10),
        date: el.dataset.date || "",
        dateDisplay: el.dataset.dateDisplay || "",
        user: el.dataset.user || "—",
        id: el.dataset.id || "",
        actionsHTML: actions ? actions.innerHTML : "",
      };
    });
  }

  _loadView() {
    let stored = null;
    try { stored = localStorage.getItem(this._storageKey); } catch (e) { /* unavailable */ }
    return stored || this.getAttribute("default-view") || "tiles";
  }

  _saveView() {
    try { localStorage.setItem(this._storageKey, this._view); } catch (e) { /* unavailable */ }
  }

  // --- rendering ----------------------------------------------------------

  _render() {
    this.innerHTML = `
      <div class="fb-toolbar">
        <div class="fb-toolbar-left">
          <div class="fb-search control has-icons-left">
            <input class="input is-small" type="text" placeholder="Filter files…" aria-label="Filter files">
            <span class="icon is-small is-left"><span class="material-icons" aria-hidden="true">search</span></span>
          </div>
          <div class="fb-chips buttons has-addons"></div>
          <div class="fb-user select is-small"></div>
        </div>
        <div class="fb-toolbar-right">
          <div class="fb-sort select is-small">
            <select aria-label="Sort by">
              <option value="date">Date</option>
              <option value="name">Name</option>
              <option value="size">Size</option>
              <option value="type">Type</option>
              <option value="user">Uploader</option>
            </select>
          </div>
          <button type="button" class="button is-small fb-sortdir" title="Toggle sort direction">
            <span class="icon"><span class="material-icons" aria-hidden="true">arrow_downward</span></span>
          </button>
          <div class="fb-viewtoggle buttons has-addons">
            <button type="button" class="button is-small" data-view="tiles" title="Tiles">
              <span class="icon"><span class="material-icons" aria-hidden="true">grid_view</span></span>
            </button>
            <button type="button" class="button is-small" data-view="list" title="List">
              <span class="icon"><span class="material-icons" aria-hidden="true">view_list</span></span>
            </button>
          </div>
        </div>
      </div>
      <div class="fb-body"></div>
    `;

    this._buildChips();
    this._buildUserFilter();
    this._wireToolbar();
    this._syncToolbarState();
    this._renderBody();
  }

  _buildChips() {
    const present = new Set(this._items.map((i) => i.type));
    const chips = [["all", "All"]];
    if (present.has("image")) chips.push(["image", "Images"]);
    if (present.has("document")) chips.push(["document", "Documents"]);
    if (present.has("video")) chips.push(["video", "Video"]);
    const wrap = this.querySelector(".fb-chips");
    wrap.innerHTML = chips
      .map(([v, label]) => `<button type="button" class="button is-small" data-type="${v}">${label}</button>`)
      .join("");
  }

  _buildUserFilter() {
    const users = Array.from(new Set(this._items.map((i) => i.user))).sort();
    const wrap = this.querySelector(".fb-user");
    if (users.length < 2) { wrap.remove(); return; }
    wrap.innerHTML =
      `<select aria-label="Filter by uploader"><option value="all">Anyone</option>` +
      users.map((u) => `<option value="${this._attr(u)}">${this._esc(u)}</option>`).join("") +
      `</select>`;
  }

  _wireToolbar() {
    this.querySelector(".fb-search input").addEventListener("input", (e) => {
      this._search = e.target.value.trim().toLowerCase();
      this._renderBody();
    });
    this.querySelectorAll(".fb-chips button").forEach((b) =>
      b.addEventListener("click", () => {
        this._typeFilter = b.dataset.type;
        this._syncToolbarState();
        this._renderBody();
      })
    );
    const userSel = this.querySelector(".fb-user select");
    if (userSel) userSel.addEventListener("change", (e) => {
      this._userFilter = e.target.value;
      this._renderBody();
    });
    this.querySelector(".fb-sort select").addEventListener("change", (e) => {
      this._sortKey = e.target.value;
      this._renderBody();
    });
    this.querySelector(".fb-sortdir").addEventListener("click", () => {
      this._sortDir = this._sortDir === "asc" ? "desc" : "asc";
      this._syncToolbarState();
      this._renderBody();
    });
    this.querySelectorAll(".fb-viewtoggle button").forEach((b) =>
      b.addEventListener("click", () => {
        this._view = b.dataset.view;
        this._saveView();
        this._syncToolbarState();
        this._renderBody();
      })
    );
  }

  _syncToolbarState() {
    this.querySelectorAll(".fb-chips button").forEach((b) =>
      b.classList.toggle("is-link", b.dataset.type === this._typeFilter)
    );
    this.querySelectorAll(".fb-viewtoggle button").forEach((b) =>
      b.classList.toggle("is-link", b.dataset.view === this._view)
    );
    const icon = this.querySelector(".fb-sortdir .material-icons");
    if (icon) icon.textContent = this._sortDir === "asc" ? "arrow_upward" : "arrow_downward";
  }

  // --- filtering / sorting ------------------------------------------------

  _visibleItems() {
    let items = this._items.filter((i) => {
      if (this._typeFilter !== "all" && i.type !== this._typeFilter) return false;
      if (this._userFilter !== "all" && i.user !== this._userFilter) return false;
      if (this._search) {
        const hay = (i.name + " " + i.caption).toLowerCase();
        if (!hay.includes(this._search)) return false;
      }
      return true;
    });

    const dir = this._sortDir === "asc" ? 1 : -1;
    const key = this._sortKey;
    items.sort((a, b) => {
      let av, bv;
      if (key === "size") { av = a.size; bv = b.size; }
      else if (key === "date") { av = a.date; bv = b.date; }
      else if (key === "type") { av = a.type; bv = b.type; }
      else if (key === "user") { av = a.user.toLowerCase(); bv = b.user.toLowerCase(); }
      else { av = a.name.toLowerCase(); bv = b.name.toLowerCase(); }
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
    return items;
  }

  _renderBody() {
    const body = this.querySelector(".fb-body");
    const items = this._visibleItems();

    if (this._items.length === 0) {
      body.innerHTML = `<p class="fb-empty has-text-grey is-size-7">No files.</p>`;
      return;
    }
    if (items.length === 0) {
      body.innerHTML = `<p class="fb-empty has-text-grey is-size-7">No files match your filters.</p>`;
      return;
    }
    body.innerHTML = this._view === "list" ? this._listHTML(items) : this._tilesHTML(items);
  }

  _thumbHTML(i) {
    if (i.type === "image" && i.thumb) {
      return `<img src="${this._attr(i.thumb)}" alt="" loading="lazy">`;
    }
    return `<span class="material-icons" aria-hidden="true">${i.type === "video" ? "movie" : "description"}</span>`;
  }

  _tilesHTML(items) {
    // When filtered to Images, use large vertical gallery cards (thumbnail on
    // top). For All / Documents / Video, use compact horizontal mini-cards.
    const images = this._typeFilter === "image";
    const grid = images ? "fb-grid fb-grid--images" : "fb-grid";
    const tile = images ? (i) => this._imageTileHTML(i) : (i) => this._rowTileHTML(i);
    return `<div class="${grid}">${items.map(tile).join("")}</div>`;
  }

  _rowTileHTML(i) {
    return `
      <div class="fb-tile">
        <a class="fb-tile-link" href="${this._attr(i.href)}" title="${this._attr(i.name)}">
          <span class="fb-thumb">${this._thumbHTML(i)}</span>
          <span class="fb-meta">
            <span class="fb-name">${this._esc(i.name)}</span>
            ${i.caption ? `<span class="fb-caption">${this._esc(i.caption)}</span>` : ""}
          </span>
        </a>
        ${i.actionsHTML ? `<span class="fb-tile-actions">${i.actionsHTML}</span>` : ""}
      </div>`;
  }

  _imageTileHTML(i) {
    return `
      <div class="fb-tile">
        <a class="fb-tile-link" href="${this._attr(i.href)}" title="${this._attr(i.name)}">
          <span class="fb-thumb">${this._thumbHTML(i)}</span>
          <span class="fb-meta">
            <span class="fb-name">${this._esc(i.name)}</span>
            ${i.caption ? `<span class="fb-caption">${this._esc(i.caption)}</span>` : ""}
            <span class="fb-sub">${this._fmtSize(i.size)} · ${this._esc(i.dateDisplay)}</span>
          </span>
        </a>
        ${i.actionsHTML ? `<span class="fb-tile-actions">${i.actionsHTML}</span>` : ""}
      </div>`;
  }

  _listHTML(items) {
    const header = (key, label, extra = "") =>
      `<th class="fb-th ${extra}" data-key="${key}">${label}` +
      (this._sortKey === key ? ` <span class="material-icons fb-th-arrow" aria-hidden="true">${this._sortDir === "asc" ? "arrow_upward" : "arrow_downward"}</span>` : "") +
      `</th>`;

    const rows = items.map((i) => `
      <tr>
        <td class="fb-td-name">
          <a href="${this._attr(i.href)}" title="${this._attr(i.name)}">
            <span class="icon is-small"><span class="material-icons" aria-hidden="true">${i.type === "image" ? "image" : i.type === "video" ? "movie" : "description"}</span></span>
            <span>${this._esc(i.name)}</span>
          </a>
          ${i.caption ? `<span class="fb-row-caption">${this._esc(i.caption)}</span>` : ""}
        </td>
        <td>${this._esc(i.type)}</td>
        <td class="fb-num">${this._fmtSize(i.size)}</td>
        <td>${this._esc(i.user)}</td>
        <td>${this._esc(i.dateDisplay)}</td>
        <td class="fb-td-actions">${i.actionsHTML || ""}</td>
      </tr>`).join("");

    const html = `<table class="fb-table table is-fullwidth is-narrow is-hoverable">
      <thead><tr>
        ${header("name", "Name")}
        ${header("type", "Type")}
        ${header("size", "Size", "fb-num")}
        ${header("user", "Uploaded by")}
        ${header("date", "Date")}
        <th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;

    // Defer wiring of sortable headers until after insertion.
    queueMicrotask(() => {
      this.querySelectorAll(".fb-th").forEach((th) =>
        th.addEventListener("click", () => {
          const key = th.dataset.key;
          if (this._sortKey === key) {
            this._sortDir = this._sortDir === "asc" ? "desc" : "asc";
          } else {
            this._sortKey = key;
            this._sortDir = key === "date" || key === "size" ? "desc" : "asc";
          }
          this.querySelector(".fb-sort select").value = this._sortKey;
          this._syncToolbarState();
          this._renderBody();
        })
      );
    });

    return html;
  }

  // --- helpers ------------------------------------------------------------

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

customElements.define("file-browser", FileBrowser);
