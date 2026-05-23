/**
 * Dual listbox web component for assign/remove workflows.
 *
 * Usage:
 * <dual-listbox
 *   left-label="Available"
 *   right-label="Selected"
 *   add-endpoint="/api/add/"
 *   remove-endpoint="/api/remove/">
 *   <left-listbox>
 *     <li value="1">Item One</li>
 *     <li value="2">Item Two</li>
 *   </left-listbox>
 *   <right-listbox>
 *     <li value="3">Item Three</li>
 *   </right-listbox>
 * </dual-listbox>
 *
 * Events dispatched (bubble):
 *   dual-listbox-add    { detail: { values, labels } }
 *   dual-listbox-remove { detail: { values, labels } }
 *
 * If add-endpoint / remove-endpoint are set, a FormData POST is fired
 * with values[] for each moved item. CSRF token is read from the
 * X-CSRFToken meta tag or cookie named "csrftoken" if present.
 */
class DualListbox extends HTMLElement {
  connectedCallback() {
    this._leftLabel  = this.getAttribute('left-label')  || 'Available';
    this._rightLabel = this.getAttribute('right-label') || 'Selected';
    this._addEndpoint    = this.getAttribute('add-endpoint')    || null;
    this._removeEndpoint = this.getAttribute('remove-endpoint') || null;

    // Extract item data BEFORE replacing innerHTML.
    const leftItems  = this._extractItems('left-listbox');
    const rightItems = this._extractItems('right-listbox');

    // Unique suffix so multiple instances don't share IDs.
    const uid = Math.random().toString(36).slice(2, 9);

    this.innerHTML = this._buildHTML(uid);

    this._fillSelect(this.querySelector(`#dlb-l-${uid}`), leftItems);
    this._fillSelect(this.querySelector(`#dlb-r-${uid}`), rightItems);
    this._updateRightCount(uid);
    this._bind(uid);
  }

  // ── private ──────────────────────────────────────────────────────────────

  _extractItems(tag) {
    const box = this.querySelector(tag);
    if (!box) return [];
    return [...box.querySelectorAll('li')].map(li => ({
      value: li.getAttribute('value') ?? li.textContent.trim(),
      label: li.textContent.trim(),
    }));
  }

  _fillSelect(select, items) {
    items.forEach(({ value, label }) => select.appendChild(new Option(label, value)));
  }

  _buildHTML(uid) {
    const ll = this._escAttr(this._leftLabel);
    const rl = this._escAttr(this._rightLabel);
    const selectStyle = [
      'width:100%',
      'height:12rem',
      'border:1px solid var(--bulma-border)',
      'padding:0.25rem',
      'background:var(--bulma-scheme-main)',
      'color:var(--bulma-text)',
      'font-size:0.875rem',
      'outline:none',
    ].join(';');

    return `
<div class="columns is-variable is-3 is-align-items-center">

  <!-- Left column -->
  <div class="column">
    <h4 class="title is-6 mb-1">${this._escHTML(this._leftLabel)}</h4>
    <p class="is-size-7 has-text-grey mb-2">
      Select items then press the forward arrow to move them.
    </p>
    <div class="field mb-1">
      <input type="search" id="dlb-fl-${uid}" class="input is-small"
        placeholder="Filter" autocomplete="off" aria-label="Filter ${ll}">
    </div>
    <div style="display:flex;flex-direction:column;">
      <select id="dlb-l-${uid}" multiple aria-label="${ll}"
        style="${selectStyle}"></select>
      <button type="button" id="dlb-sall-l-${uid}"
        class="button is-small is-fullwidth" style="border-top:none;"
        title="Select all visible items for addition">
        Select all for addition
      </button>
    </div>
  </div>

  <!-- Centre arrows -->
  <div class="column is-narrow"
    style="display:flex;flex-direction:column;gap:0.5rem;align-items:center;">
    <button type="button" id="dlb-add-${uid}" class="button is-small"
      title="Move selected items to ${rl}"
      aria-label="Add selected items to ${rl}">
      <span class="icon">
        <span class="material-icons" aria-hidden="true">arrow_forward</span>
      </span>
    </button>
    <button type="button" id="dlb-rem-${uid}" class="button is-small"
      title="Move selected items back to ${ll}"
      aria-label="Remove selected items back to ${ll}">
      <span class="icon">
        <span class="material-icons" aria-hidden="true">arrow_back</span>
      </span>
    </button>
  </div>

  <!-- Right column -->
  <div class="column">
    <h4 class="title is-6 mb-1" id="dlb-rtitle-${uid}">
      ${this._escHTML(this._rightLabel)} (0)
    </h4>
    <p class="is-size-7 has-text-grey mb-2">
      Select items then press the back arrow to remove them.
    </p>
    <div class="field mb-1">
      <input type="search" id="dlb-fr-${uid}" class="input is-small"
        placeholder="Filter" autocomplete="off" aria-label="Filter ${rl}">
    </div>
    <div style="display:flex;flex-direction:column;">
      <select id="dlb-r-${uid}" multiple aria-label="${rl}"
        style="${selectStyle}"></select>
      <button type="button" id="dlb-sall-r-${uid}"
        class="button is-small is-fullwidth" style="border-top:none;"
        title="Select all visible items for removal">
        Select all for removal
      </button>
    </div>
  </div>

</div>`;
  }

  _bind(uid) {
    const lSel  = this.querySelector(`#dlb-l-${uid}`);
    const rSel  = this.querySelector(`#dlb-r-${uid}`);
    const fLeft = this.querySelector(`#dlb-fl-${uid}`);
    const fRight = this.querySelector(`#dlb-fr-${uid}`);

    fLeft.addEventListener('input', () => this._applyFilter(lSel, fLeft.value));
    fRight.addEventListener('input', () => this._applyFilter(rSel, fRight.value));

    this.querySelector(`#dlb-add-${uid}`)
      .addEventListener('click', () => this._move(lSel, rSel, uid, 'add'));
    this.querySelector(`#dlb-rem-${uid}`)
      .addEventListener('click', () => this._move(rSel, lSel, uid, 'remove'));

    this.querySelector(`#dlb-sall-l-${uid}`)
      .addEventListener('click', () => this._selectAllVisible(lSel));
    this.querySelector(`#dlb-sall-r-${uid}`)
      .addEventListener('click', () => this._selectAllVisible(rSel));
  }

  _applyFilter(select, query) {
    const q = query.trim().toLowerCase();
    [...select.options].forEach(opt => {
      opt.hidden = q ? !opt.text.toLowerCase().includes(q) : false;
    });
  }

  _selectAllVisible(select) {
    [...select.options].filter(o => !o.hidden).forEach(o => (o.selected = true));
  }

  _move(fromSel, toSel, uid, action) {
    const selected = [...fromSel.selectedOptions];
    if (!selected.length) return;

    const moved = selected.map(o => ({ value: o.value, label: o.text }));

    selected.forEach(opt => {
      fromSel.removeChild(opt);
      opt.selected = false;
      opt.hidden   = false;
      this._insertSorted(toSel, opt);
    });

    this._updateRightCount(uid);

    const endpoint = action === 'add' ? this._addEndpoint : this._removeEndpoint;
    if (endpoint) this._post(endpoint, moved);

    this.dispatchEvent(new CustomEvent(`dual-listbox-${action}`, {
      bubbles: true,
      composed: true,
      detail: {
        values: moved.map(i => i.value),
        labels: moved.map(i => i.label),
      },
    }));
  }

  _insertSorted(select, opt) {
    const after = [...select.options].find(o => o.value > opt.value);
    after ? select.insertBefore(opt, after) : select.appendChild(opt);
  }

  _updateRightCount(uid) {
    const rSel   = this.querySelector(`#dlb-r-${uid}`);
    const titleEl = this.querySelector(`#dlb-rtitle-${uid}`);
    if (titleEl && rSel) {
      titleEl.textContent = `${this._rightLabel} (${rSel.options.length})`;
    }
  }

  _post(endpoint, moved) {
    const fd = new FormData();
    moved.forEach(item => fd.append('values[]', item.value));
    const csrf = this._csrf();
    if (csrf) fd.append('csrfmiddlewaretoken', csrf);
    fetch(endpoint, { method: 'POST', body: fd })
      .catch(err => console.error('[dual-listbox] POST error:', err));
  }

  _csrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.content;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : null;
  }

  _escHTML(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  _escAttr(str) {
    return String(str).replace(/"/g, '&quot;');
  }
}

if (!customElements.get('dual-listbox')) {
  customElements.define('dual-listbox', DualListbox);
}
