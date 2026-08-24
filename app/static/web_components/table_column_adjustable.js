/**
 * <table-column-adjustable> — light-DOM wrapper that makes a plain <table>'s
 * columns user-resizable by dragging the right edge of each header cell.
 *
 * Design intent
 * -------------
 * Style-only / utility-only wrapper, same contract as <list-box>: the
 * user-supplied <table> stays exactly where it is in the light DOM (never
 * moved into Shadow DOM, never re-rendered), so hx-* attributes, form
 * inputs, and event listeners inside it survive untouched. The component
 * only injects a <colgroup> (if one isn't already present) and a small
 * drag handle into each header cell.
 *
 * Column widths are driven entirely by the <colgroup>'s <col> widths, with
 * `table-layout: fixed` on the table. Each header cell's own inline
 * `style="width:…"` (if any) seeds the matching <col>'s starting width —
 * so an existing `<th style="width:8rem;">` still gives that column its
 * initial size, it just becomes adjustable afterward.
 *
 * Usage
 * -----
 *   <table-column-adjustable>
 *     <table class="table is-fullwidth">
 *       <thead><tr><th style="width:8rem;">Unit cost</th>...</tr></thead>
 *       <tbody>...</tbody>
 *     </table>
 *   </table-column-adjustable>
 *
 * Attributes
 *   min-width   minimum column width in px. Default 40.
 *
 * Re-initializes automatically after an HTMX swap replaces its contents
 * (MutationObserver), same as <list-box>.
 */
(function () {
  if (!document.getElementById('table-column-adjustable-styles')) {
    const style = document.createElement('style');
    style.id = 'table-column-adjustable-styles';
    style.textContent = `
      table-column-adjustable { display: block; overflow-x: auto; max-width: 100%; }
      table-column-adjustable table { table-layout: fixed; }
      table-column-adjustable th { position: relative; }
      table-column-adjustable .tca-handle {
        position: absolute;
        top: 0;
        right: -3px;
        width: 6px;
        height: 100%;
        cursor: col-resize;
        z-index: 2;
        touch-action: none;
      }
      table-column-adjustable .tca-handle:hover,
      table-column-adjustable .tca-handle.is-active {
        background: var(--bulma-link);
        opacity: 0.5;
      }
      table-column-adjustable.is-resizing { cursor: col-resize; user-select: none; }
    `;
    document.head.appendChild(style);
  }

  class TableColumnAdjustable extends HTMLElement {
    connectedCallback() {
      if (this._ready) return;
      this._tryInit();
      if (!this._ready) {
        this._observer = new MutationObserver(() => this._tryInit());
        this._observer.observe(this, { childList: true, subtree: true });
      }
    }

    disconnectedCallback() {
      this._observer?.disconnect();
    }

    _tryInit() {
      const table = this.querySelector('table');
      const headerRow = table?.querySelector('thead tr');
      if (!table || !headerRow) return;

      this._ready = true;
      this._observer?.disconnect();

      const minWidth = parseInt(this.getAttribute('min-width'), 10) || 40;
      const headers = Array.from(headerRow.children).filter(
        (el) => el.tagName === 'TH' || el.tagName === 'TD'
      );

      let colgroup = table.querySelector('colgroup');
      if (!colgroup) {
        colgroup = document.createElement('colgroup');
        headers.forEach((th) => {
          const col = document.createElement('col');
          const seeded = th.style.width || `${th.getBoundingClientRect().width}px`;
          col.style.width = seeded;
          colgroup.appendChild(col);
        });
        table.insertBefore(colgroup, table.firstChild);
      }
      const cols = Array.from(colgroup.children);

      headers.forEach((th, index) => {
        const col = cols[index];
        if (!col || th.querySelector('.tca-handle')) return;

        const handle = document.createElement('span');
        handle.className = 'tca-handle';
        handle.setAttribute('aria-hidden', 'true');
        th.appendChild(handle);

        handle.addEventListener('pointerdown', (event) => {
          event.preventDefault();
          const startX = event.clientX;
          const startWidth = col.getBoundingClientRect().width;
          handle.classList.add('is-active');
          this.classList.add('is-resizing');
          handle.setPointerCapture(event.pointerId);

          const onMove = (moveEvent) => {
            const delta = moveEvent.clientX - startX;
            const width = Math.max(minWidth, Math.round(startWidth + delta));
            col.style.width = `${width}px`;
          };
          const onUp = (upEvent) => {
            handle.releasePointerCapture(upEvent.pointerId);
            handle.classList.remove('is-active');
            this.classList.remove('is-resizing');
            handle.removeEventListener('pointermove', onMove);
            handle.removeEventListener('pointerup', onUp);
          };
          handle.addEventListener('pointermove', onMove);
          handle.addEventListener('pointerup', onUp, { once: true });
        });
      });
    }
  }

  customElements.define('table-column-adjustable', TableColumnAdjustable);
})();
