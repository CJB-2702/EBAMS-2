/**
 * <dual-list-box> — light-DOM, layout-only wrapper for two <list-box>es and
 * a stack of move controls.
 *
 * Design intent
 * -------------
 * Pure styling layer. No JavaScript coordination, no events, no innerHTML
 * mutations. The component exists so the page can declare:
 *
 *   <dual-list-box id="groups-mgr">
 *     <list-box slot="left"  id="groups-avail" label="Available">…</list-box>
 *     <div slot="controls">
 *       <button hx-post="/…/add"
 *               hx-vals='js:{ids: listBox("groups-avail").selected()}'
 *               hx-target="#groups-mgr" hx-swap="outerHTML">→</button>
 *       <button hx-post="/…/remove"
 *               hx-vals='js:{ids: listBox("groups-held").selected()}'
 *               hx-target="#groups-mgr" hx-swap="outerHTML">←</button>
 *     </div>
 *     <list-box slot="right" id="groups-held"  label="Held">…</list-box>
 *   </dual-list-box>
 *
 * The component is HTMX-agnostic. The page may swap:
 *   • the entire <dual-list-box>      (hx-target="#groups-mgr" outerHTML)
 *   • a single <list-box>             (hx-target="#groups-avail" outerHTML)
 *   • just the <select> inside one    (hx-target="#groups-avail" find select)
 *   • the parent card                 (hx-target="closest .card-content")
 * …all from the same markup.
 *
 * Slots (light-DOM, slot attribute on direct children)
 *   slot="left"      the left <list-box>      (or any element)
 *   slot="controls"  the centre stack of move buttons
 *   slot="right"     the right <list-box>     (or any element)
 *
 * No public JS API and no custom events. This is intentional — coordination
 * lives in HTMX attributes on the controls, not in the wrapper.
 */
(function () {
  if (!document.getElementById('dual-list-box-styles')) {
    const style = document.createElement('style');
    style.id = 'dual-list-box-styles';
    style.textContent = `
      dual-list-box {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        gap: 0.75rem;
        align-items: center;
      }
      dual-list-box > [slot="left"]  { grid-column: 1; align-self: stretch; }
      dual-list-box > [slot="controls"] {
        grid-column: 2;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        align-items: center;
      }
      dual-list-box > [slot="right"] { grid-column: 3; align-self: stretch; }
    `;
    document.head.appendChild(style);
  }

  class DualListBox extends HTMLElement {
    // No connectedCallback needed — layout is pure CSS. The class exists
    // so callers can do `document.querySelector('dual-list-box')` and get
    // a specific tag in the DOM, and so future enhancements have a home.
  }

  if (!customElements.get('dual-list-box')) {
    customElements.define('dual-list-box', DualListBox);
  }
})();
