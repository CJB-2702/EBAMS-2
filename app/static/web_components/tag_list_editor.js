/**
 * <tag-list-editor> — free-text tag/chip editor backed by hidden form inputs.
 *
 * Design intent
 * -------------
 * A small utility for editing an open-ended list of short strings (e.g. a
 * model's accepted config baselines). Add via the top input (Enter or the Add
 * button), remove via each chip's × button. The canonical value is a set of
 * hidden ``<input name="<name>">`` elements — one per tag — so the server reads
 * the list with ``post.getlist(name)``.
 *
 * F5-safe: initial values come from server-rendered hidden inputs (or a
 * ``value`` attribute), so a plain full-page reload and even a no-JS submit
 * still round-trip the current list.
 *
 * Usage
 * -----
 *   <tag-list-editor name="config_baselines" placeholder="Add a baseline…">
 *     <input type="hidden" name="config_baselines" value="LE">
 *     <input type="hidden" name="config_baselines" value="EX">
 *   </tag-list-editor>
 *
 * Attributes
 *   name         required — form field name emitted per tag (hidden inputs).
 *   placeholder  optional — placeholder for the add input.
 *   empty-text   optional — text shown when the list is empty (default "None yet.").
 *
 * Values are trimmed, de-duplicated case-insensitively (first casing wins), and
 * a comma-separated entry is split into multiple tags on add (so paste works).
 */
(function () {
  if (!document.getElementById('tag-list-editor-styles')) {
    const style = document.createElement('style');
    style.id = 'tag-list-editor-styles';
    style.textContent = `
      tag-list-editor { display: block; }
      tag-list-editor .tle-list {
        list-style: none; margin: 0.4rem 0 0 0; padding: 0;
        display: flex; flex-wrap: wrap; gap: 0.35rem;
      }
      tag-list-editor .tle-chip {
        display: inline-flex; align-items: center; gap: 0.4rem;
        background: var(--bulma-scheme-main-bis, #f5f5f5);
        border: 1px solid var(--bulma-border, #dbdbdb);
        border-radius: 0;
        padding: 0.15rem 0.15rem 0.15rem 0.5rem;
        font-size: 0.8rem; line-height: 1.4;
      }
      tag-list-editor .tle-chip .delete { margin-left: 0.1rem; }
      tag-list-editor .tle-empty { color: var(--bulma-text-weak, #7a7a7a); font-size: 0.75rem; margin-top: 0.4rem; }
    `;
    document.head.appendChild(style);
  }

  class TagListEditor extends HTMLElement {
    connectedCallback() {
      if (this._ready) return;
      // Wait for light-DOM children (initial hidden inputs) to be parsed.
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => this._init(), { once: true });
      } else {
        this._init();
      }
    }

    _init() {
      if (this._ready) return;
      this._ready = true;
      this._name = this.getAttribute('name') || 'items';
      this._placeholder = this.getAttribute('placeholder') || 'Add an item…';
      this._emptyText = this.getAttribute('empty-text') || 'None yet.';

      // Seed from server-rendered hidden inputs, else a comma-separated `value`.
      this._values = [];
      this.querySelectorAll('input[type="hidden"]').forEach((inp) => {
        this._addValue(inp.value, { silent: true });
      });
      if (this._values.length === 0 && this.getAttribute('value')) {
        this.getAttribute('value').split(',').forEach((v) => this._addValue(v, { silent: true }));
      }

      this.innerHTML = '';
      this._buildShell();
      this._render();
    }

    // ── value model ───────────────────────────────────────────────────────────
    _addValue(raw, { silent = false } = {}) {
      let added = false;
      String(raw || '').split(',').forEach((part) => {
        const value = part.trim();
        if (!value) return;
        const exists = this._values.some((v) => v.toLowerCase() === value.toLowerCase());
        if (!exists) { this._values.push(value); added = true; }
      });
      if (added && !silent) this._render();
      return added;
    }

    _removeValue(value) {
      this._values = this._values.filter((v) => v !== value);
      this._render();
    }

    // ── DOM ───────────────────────────────────────────────────────────────────
    _buildShell() {
      const addRow = document.createElement('div');
      addRow.className = 'field has-addons';
      addRow.innerHTML = `
        <div class="control is-expanded">
          <input type="text" class="input is-small tle-input" placeholder="${this._escapeAttr(this._placeholder)}" autocomplete="off">
        </div>
        <div class="control">
          <button type="button" class="button is-small is-light tle-add">Add</button>
        </div>`;
      this.appendChild(addRow);

      this._input = addRow.querySelector('.tle-input');
      this._list = document.createElement('ul');
      this._list.className = 'tle-list';
      this.appendChild(this._list);

      const commit = () => {
        if (this._addValue(this._input.value)) this._input.value = '';
        this._input.focus();
      };
      addRow.querySelector('.tle-add').addEventListener('click', commit);
      this._input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); commit(); }
      });
      // Delegate chip removal.
      this._list.addEventListener('click', (e) => {
        const btn = e.target.closest('.delete');
        if (btn) this._removeValue(btn.getAttribute('data-value'));
      });
    }

    _render() {
      this._list.innerHTML = '';
      if (this._values.length === 0) {
        const empty = document.createElement('li');
        empty.className = 'tle-empty';
        empty.textContent = this._emptyText;
        this._list.appendChild(empty);
      } else {
        this._values.forEach((value) => {
          const li = document.createElement('li');
          li.className = 'tle-chip';
          const label = document.createElement('span');
          label.textContent = value;
          const del = document.createElement('button');
          del.type = 'button';
          del.className = 'delete is-small';
          del.setAttribute('aria-label', `Remove ${value}`);
          del.setAttribute('data-value', value);
          const hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = this._name;
          hidden.value = value;
          li.append(label, del, hidden);
          this._list.appendChild(li);
        });
      }
    }

    _escapeAttr(s) {
      return String(s).replace(/"/g, '&quot;');
    }
  }

  if (!customElements.get('tag-list-editor')) {
    customElements.define('tag-list-editor', TagListEditor);
  }
})();
