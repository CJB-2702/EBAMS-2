// DELIBERATE ANTI PATTERN: THIS WEBCOMPONENT MANUALLY ADDS BULMA COMPONENETS AND UI ELEMENTS
// THIS IS DONE SO THAT IT CAN BE USED AS A DROP IN REPLACEMENT FOR BULMA SEARCH DROPDOWNS
// THIS IS AN EXCPTION BECAUSE ITS INTERACTION IS SO UNIFORM AND SIMPLE ITS EASIER
// TO JUST ADD THE STYLES

class SearchDropdown extends HTMLElement {
  static formAssociated = true;

  constructor() {
    super();
    this.internals = this.attachInternals();
    this.attachShadow({ mode: "open" });
    this._value = "";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          position: relative;
          width: 100%;
          font-family: var(--app-font-mono-input, monospace);
        }
        input {
          width: 100%;
          box-sizing: border-box;
          border: 1px solid var(--bulma-border);
          border-radius: var(--bulma-radius);
          box-shadow: inset 0 0.0625em 0.125em rgba(10, 10, 10, 0.05);
          display: block;
          font-family: var(--app-font-mono-input, monospace);
          font-size: 1rem;
          height: 2.5em;
          line-height: 1.5;
          padding: calc(0.5em - 1px) calc(0.75em - 1px);
          background-color: var(--bulma-scheme-main);
          color: var(--bulma-text);
        }
        input:hover { border-color: var(--bulma-border-hover, var(--bulma-text-weak)); }
        input:focus {
          border-color: var(--bulma-primary);
          box-shadow: 0 0 0 0.125em hsla(var(--bulma-primary-h), var(--bulma-primary-s), var(--bulma-primary-l), 0.25);
          outline: none;
        }
        input::placeholder { color: var(--bulma-text-weak); opacity: 0.6; }
        .dropdown {
          position: absolute;
          left: 0;
          right: 0;
          top: calc(100% + 2px);
          z-index: 20;
          display: none;
          list-style: none;
          margin: 0;
          padding: 0.5rem 0;
          background-color: var(--bulma-scheme-main);
          border: 1px solid var(--bulma-border);
          border-radius: var(--bulma-radius);
          box-shadow: 0 0.5em 1em -0.125em rgba(10, 10, 10, 0.25), 0 0 0 1px var(--bulma-border-weak);
          max-height: 16rem;
          overflow-y: auto;
        }
        :host([open]) .dropdown { display: block; }
        ::slotted(li) {
          padding: 0.5rem 0.75rem;
          cursor: pointer;
          font-size: 0.875rem;
          line-height: 1.4;
          color: var(--bulma-text);
        }
        ::slotted(li):hover,
        ::slotted(li):focus {
          background-color: var(--bulma-scheme-main-bis);
        }
        ::slotted(li.is-disabled),
        ::slotted(li[aria-disabled="true"]) {
          cursor: default;
          color: var(--bulma-text-weak);
        }
        ::slotted(li.is-family-monospace) {
          font-family: var(--app-font-mono-input, monospace);
          font-size: 0.8125rem;
        }
      </style>
      <input type="text" autocomplete="off" placeholder="Search…">
      <ul class="dropdown" role="listbox">
        <slot></slot>
      </ul>
    `;
  }

  static get observedAttributes() {
    return ["value-label"];
  }

  attributeChangedCallback(name, oldValue, newValue) {
    // Keeps the visible text in sync with `value-label` even when something
    // other than this component's own click handler updates the attribute
    // in place (e.g. an htmx swap that patches attributes on the existing
    // node instead of replacing it). Without this, the shadow-DOM <input>'s
    // displayed text can silently go stale — showing whatever was last
    // written locally — while the reflected attribute has already moved on.
    if (name !== "value-label" || !this.input || newValue === oldValue) {
      return;
    }
    this.input.value = newValue || "";
  }

  connectedCallback() {
    // Guard against re-running init (and re-stacking event listeners) if
    // the browser ever calls connectedCallback again on an already-set-up
    // instance (disconnect/reconnect without the node being recreated).
    if (this._ready) return;
    this._ready = true;

    this.input = this.shadowRoot.querySelector("input");

    const passThrough = [
      "hx-get",
      "hx-post",
      "hx-trigger",
      "hx-target",
      "hx-swap",
      "hx-indicator",
      "hx-headers",
      "hx-vals",
      "hx-params",
      "hx-include",
      "hx-sync",
    ];
    passThrough.forEach((attr) => {
      if (this.hasAttribute(attr)) {
        this.input.setAttribute(attr, this.getAttribute(attr));
      }
    });

    if (this.hasAttribute("placeholder")) {
      this.input.setAttribute("placeholder", this.getAttribute("placeholder"));
    }

    if (!this.input.hasAttribute("hx-trigger")) {
      this.input.setAttribute("hx-trigger", "keyup changed delay:350ms, search");
    }

    if (!this.input.hasAttribute("hx-target")) {
      if (!this.id) {
        this.id = `search-dropdown-${Math.random().toString(36).slice(2, 11)}`;
      }
      // HTMX resolves bare #id from the trigger's root (shadow root here), so the host id is invisible.
      // "global " forces document-scoped querySelector (htmx hx-target extended syntax).
      this.input.setAttribute("hx-target", `global #${this.id}`);
    }

    if (!this.input.hasAttribute("hx-swap")) {
      this.input.setAttribute("hx-swap", "innerHTML");
    }

    this.input.setAttribute("name", "q");

    if (this.hasAttribute("value")) {
      this.value = this.getAttribute("value");
    }
    if (this.hasAttribute("value-label")) {
      this.input.value = this.getAttribute("value-label");
    }

    this.input.addEventListener("input", () => {
      if (this.input.value.trim() === "") {
        this.value = "";
      }
    });

    if (window.htmx) {
      htmx.process(this.input);
    }

    this.addEventListener("click", (e) => {
      const li = e.target.closest("li");
      if (!li || !this.contains(li)) {
        return;
      }
      if (!li.hasAttribute("data-value")) {
        return;
      }
      const raw = li.getAttribute("data-value");
      if (raw === null || raw === "") {
        return;
      }
      this.value = raw;
      // Routed through the attribute (not a direct `this.input.value =`
      // write) so attributeChangedCallback is the one place that updates
      // the visible text — see the comment there.
      this.setAttribute("value-label", li.innerText.trim());
      this.removeAttribute("open");
      // Form-associated custom elements don't fire a native "change" on their
      // own — internals.setFormValue() is silent. Dispatch one explicitly
      // (composed so it crosses the shadow boundary) so ancestor forms using
      // hx-trigger="change" or a plain change listener see the pick.
      this.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    });

    this.input.addEventListener("focus", () => this.setAttribute("open", ""));
    this.input.addEventListener("blur", () => {
      setTimeout(() => this.removeAttribute("open"), 200);
    });
  }

  get value() {
    return this._value;
  }

  set value(v) {
    this._value = v;
    this.setAttribute("value", v);
    this.internals.setFormValue(v);
  }

  get name() {
    return this.getAttribute("name");
  }
}

if (!customElements.get("search-dropdown")) {
  customElements.define("search-dropdown", SearchDropdown);
}
