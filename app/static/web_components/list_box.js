/**
 * <list-box> — light-DOM wrapper around a <select multiple>.
 *
 * Design intent
 * -------------
 * Style-only / utility-only wrapper. We never call this.innerHTML on the
 * host, never move into Shadow DOM. User-supplied <select>, <input>, and
 * <button> elements are re-parented into a generated shell so their
 * hx-* attributes, event listeners, and Django template content survive.
 *
 * That means HTMX can target the inner <select> directly (e.g. swap its
 * <option> set) and our event delegation, which lives on the host, keeps
 * working across swaps.
 *
 * Usage
 * -----
 *   <list-box id="avail" label="Available groups">
 *     <input slot="search" type="search" class="input is-small"
 *            placeholder="Filter"
 *            hx-get="/admin/foo?format=htmx-options"
 *            hx-trigger="input changed delay:300ms"
 *            hx-target="closest list-box find select"
 *            hx-swap="innerHTML">
 *     <select slot="options" multiple>
 *       <option value="1" data-extra="anything">Group One</option>
 *     </select>
 *     <button slot="action" class="button is-small">Custom action</button>
 *   </list-box>
 *
 * Slots (light-DOM, slot attribute)
 *   slot="search"  optional — filter input. Default: local-filter <input>.
 *   slot="options" required — the <select multiple>. Default: empty <select>.
 *   slot="action"  optional — bottom action button. Default: "Select all visible".
 *
 * Attributes
 *   label       optional <h4> heading text. Omitted when missing.
 *   description optional helper line under the heading.
 *   height      list height (CSS unit). Default "12rem".
 *
 * Public API
 *   el.select            → underlying <select> element (for HTMX targeting)
 *   el.items()           → [value, value, ...] — all option values
 *   el.itemsDicts()      → [{value, label, ...dataset}, ...]
 *   el.selected()        → [value, value, ...] — selected option values
 *   el.selectedDicts()   → [{value, label, ...dataset}, ...]
 *   el.selectAll()       → select every non-hidden option, fires change
 *   el.clear()           → deselect everything, fires change
 *
 * Events (bubble, composed)
 *   list-box-change   { detail: { values, labels } }   on selection change
 *   list-box-scroll-end                                when option list
 *     scrolled to bottom (hook for HTMX-driven infinite scroll)
 *
 * Global helper
 *   window.listBox(id)  → shorthand for document.getElementById(id)
 *                          (intended for terse hx-vals js: expressions)
 */
(function () {
  // One-time CSS injection. Kept tiny — relies on Bulma vars already loaded.
  if (!document.getElementById('list-box-styles')) {
    const style = document.createElement('style');
    style.id = 'list-box-styles';
    style.textContent = `
      list-box { display: block; }
      list-box .lb-shell { display: flex; flex-direction: column; }
      list-box .lb-options-wrap { display: flex; flex-direction: column; }
      list-box select[data-lb-select] {
        width: 100%;
        border: 1px solid var(--bulma-border);
        padding: 0.25rem;
        background: var(--bulma-scheme-main);
        color: var(--bulma-text);
        font-size: 0.875rem;
        outline: none;
      }
      list-box .lb-action {
        border-top: none;
      }
    `;
    document.head.appendChild(style);
  }

  class ListBox extends HTMLElement {
    connectedCallback() {
      if (this._ready) return;
      this._tryInit();
      if (!this._ready) {
        // Children may not yet be parsed (programmatic creation, htmx swap, etc).
        this._observer = new MutationObserver(() => this._tryInit());
        this._observer.observe(this, { childList: true });
      }
    }

    disconnectedCallback() {
      this._observer?.disconnect();
    }

    // ── public API ──────────────────────────────────────────────────────────

    get select() {
      return this._select;
    }

    items() {
      return [...this._select.options].map(o => o.value);
    }

    itemsDicts() {
      return [...this._select.options].map(o => this._optionDict(o));
    }

    selected() {
      return [...this._select.selectedOptions].map(o => o.value);
    }

    selectedDicts() {
      return [...this._select.selectedOptions].map(o => this._optionDict(o));
    }

    selectAll() {
      [...this._select.options]
        .filter(o => !o.hidden)
        .forEach(o => (o.selected = true));
      this._emitChange();
    }

    clear() {
      [...this._select.options].forEach(o => (o.selected = false));
      this._emitChange();
    }

    // ── private ─────────────────────────────────────────────────────────────

    _tryInit() {
      // Require the <select slot="options"> before initializing; without it
      // we have no list to manage and there is no useful default behaviour.
      // (A default empty <select> is still rendered if the slot is missing
      //  entirely — handled below — but we wait one tick for parsing.)
      const select = this._findSlot('options', 'select');
      const search = this._findSlot('search');
      const action = this._findSlot('action');

      // If nothing has been parsed yet, wait. Otherwise, proceed even if
      // some slots are absent — defaults cover them.
      if (!select && !search && !action && this.children.length === 0) return;

      this._observer?.disconnect();
      this._ready = true;

      this._label       = this.getAttribute('label') || '';
      this._description = this.getAttribute('description') || '';
      this._height      = this.getAttribute('height') || '12rem';

      // Detach slotted nodes so we can re-mount them inside the shell.
      const userSelect = select || this._buildDefaultSelect();
      const userSearch = search; // may be null → default below
      const userAction = action; // may be null → default below

      userSelect.remove();
      userSearch?.remove();
      userAction?.remove();

      // Build the shell skeleton (no innerHTML on host).
      const shell = this._buildShell();
      this.appendChild(shell);

      // Mount label/description if any.
      if (this._label) {
        const h = document.createElement('h4');
        h.className = 'title is-6 mb-1';
        h.textContent = this._label;
        shell.insertBefore(h, shell.firstChild);
      }
      if (this._description) {
        const p = document.createElement('p');
        p.className = 'is-size-7 has-text-grey mb-2';
        p.textContent = this._description;
        const anchor = shell.querySelector('.lb-search-wrap');
        shell.insertBefore(p, anchor);
      }

      // Mount search.
      const searchSlot = shell.querySelector('.lb-search-wrap');
      if (userSearch) {
        userSearch.removeAttribute('slot');
        searchSlot.appendChild(userSearch);
        this._userSearch = true;
        this._search = userSearch;
      } else {
        const def = this._buildDefaultSearch();
        searchSlot.appendChild(def);
        this._userSearch = false;
        this._search = def;
      }

      // Mount <select>.
      const optionsSlot = shell.querySelector('.lb-options-wrap');
      userSelect.removeAttribute('slot');
      this._applySelectStyling(userSelect);
      optionsSlot.appendChild(userSelect);
      this._select = userSelect;

      // Mount action button.
      if (userAction) {
        userAction.removeAttribute('slot');
        optionsSlot.appendChild(userAction);
        this._action = userAction;
        this._defaultAction = false;
      } else {
        const def = this._buildDefaultAction();
        optionsSlot.appendChild(def);
        this._action = def;
        this._defaultAction = true;
      }

      this._bind();
    }

    _findSlot(name, tagFilter) {
      // Only consider direct children — slotted elements never nest deeper.
      for (const child of this.children) {
        if (child.getAttribute && child.getAttribute('slot') === name) {
          if (tagFilter && child.tagName.toLowerCase() !== tagFilter) continue;
          return child;
        }
      }
      return null;
    }

    _buildShell() {
      const shell = document.createElement('div');
      shell.className = 'lb-shell';

      const searchWrap = document.createElement('div');
      searchWrap.className = 'field mb-1 lb-search-wrap';

      const optsWrap = document.createElement('div');
      optsWrap.className = 'lb-options-wrap';

      shell.appendChild(searchWrap);
      shell.appendChild(optsWrap);
      return shell;
    }

    _buildDefaultSelect() {
      const sel = document.createElement('select');
      sel.setAttribute('multiple', '');
      return sel;
    }

    _buildDefaultSearch() {
      const inp = document.createElement('input');
      inp.type = 'search';
      inp.className = 'input is-small';
      inp.placeholder = 'Filter';
      inp.autocomplete = 'off';
      inp.setAttribute('aria-label', `Filter ${this._label || 'items'}`);
      return inp;
    }

    _buildDefaultAction() {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'button is-small is-fullwidth lb-action';
      btn.title = 'Select all visible items';
      btn.textContent = 'Select all visible';
      return btn;
    }

    _applySelectStyling(sel) {
      sel.setAttribute('data-lb-select', '');
      if (!sel.hasAttribute('multiple')) sel.setAttribute('multiple', '');
      if (!sel.getAttribute('aria-label') && this._label) {
        sel.setAttribute('aria-label', this._label);
      }
      // Height is set inline so callers can override per instance.
      sel.style.height = this._height;
    }

    _bind() {
      // Selection change — delegate on host so HTMX swaps of <option> survive.
      this.addEventListener('change', (e) => {
        if (e.target === this._select) this._emitChange();
      });

      // Default search: local filter over current <option>s.
      // User-provided search is left alone (caller wires HTMX or custom logic).
      if (!this._userSearch && this._search) {
        this._search.addEventListener('input', () => {
          const q = this._search.value.trim().toLowerCase();
          [...this._select.options].forEach(o => {
            o.hidden = q ? !o.text.toLowerCase().includes(q) : false;
          });
        });
      }

      // Default action button → select all visible. User-provided actions
      // are not auto-wired (the caller decides what the button does).
      if (this._defaultAction) {
        this._action.addEventListener('click', () => this.selectAll());
      }

      // Infinite-scroll hook. Fires once per "near-bottom" arrival so HTMX
      // listeners can run e.g. hx-trigger="list-box-scroll-end from:closest list-box"
      this._select.addEventListener('scroll', () => {
        const s = this._select;
        const near = s.scrollTop + s.clientHeight >= s.scrollHeight - 8;
        if (near && !this._scrollEndFired) {
          this._scrollEndFired = true;
          this.dispatchEvent(new CustomEvent('list-box-scroll-end', {
            bubbles: true, composed: true,
          }));
        } else if (!near) {
          this._scrollEndFired = false;
        }
      });
    }

    _optionDict(opt) {
      const out = { value: opt.value, label: opt.text };
      if (opt.dataset) {
        for (const k in opt.dataset) out[k] = opt.dataset[k];
      }
      return out;
    }

    _emitChange() {
      const values = this.selected();
      const labels = this.selectedDicts().map(d => d.label);
      this.dispatchEvent(new CustomEvent('list-box-change', {
        bubbles: true, composed: true,
        detail: { values, labels },
      }));
    }
  }

  if (!customElements.get('list-box')) {
    customElements.define('list-box', ListBox);
  }

  // Terse global for hx-vals="js:{ids: listBox('foo').selected()}"
  if (!window.listBox) {
    window.listBox = (id) => document.getElementById(id);
  }
})();
