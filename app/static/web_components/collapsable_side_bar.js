// DELIBERATE ANTI PATTERN: THIS WEBCOMPONENT MANUALLY ADDS BULMA COMPONENETS AND UI ELEMENTS
// THIS IS DONE SO THAT IT CAN BE USED AS A DROP IN REPLACEMENT FOR BULMA SIDEBARS
// THIS IS AN EXCPTION BECAUSE ITS INTERACTION IS SO UNIFORM AND SIMPLE ITS EASIER
// TO JUST ADD THE STYLES

class CollapsableSideBar extends HTMLElement {
  constructor() {
    super();
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>
        :host {
          display: block;
          background: var(--bulma-scheme-main-bis);
          border-right: 1px solid var(--bulma-border);
          overflow-y: auto;
          min-width: 0;
          padding-bottom: 1rem;
        }
        :host([collapsed]) {
          overflow: hidden;
          cursor: pointer;
          padding-bottom: 0;
        }

        button {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.4rem 0.75rem;
          width: 100%;
          border: none;
          border-bottom: 1px solid var(--bulma-border-weak);
          background: none;
          color: var(--bulma-text-weak);
          font-family: inherit;
          font-size: 0.68rem;
          font-weight: 600;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          cursor: pointer;
          user-select: none;
          box-sizing: border-box;
        }
        button:hover {
          background: var(--bulma-background);
          color: var(--bulma-text);
        }

        .icon {
          font-size: 0.9rem;
          opacity: 0.65;
          display: inline-block;
          transform: rotate(90deg);
        }
        .expanded {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }
        .collapsed-view {
          display: none;
          flex-direction: column;
          align-items: center;
          width: 100%;
          padding-top: 0.2rem;
          gap: 0.15rem;
        }
        .chevron {
          font-size: 0.85rem;
          font-weight: 700;
          line-height: 1;
          color: var(--bulma-text-weak);
          opacity: 0.7;
        }
        .label {
          writing-mode: vertical-lr;
          text-orientation: upright;
          font-size: 0.55rem;
          font-weight: 700;
          letter-spacing: -0.05em;
          text-transform: uppercase;
          color: var(--bulma-text-weak);
          opacity: 0.55;
          margin-top: 0.2rem;
        }

        :host([collapsed]) button {
          flex-direction: column;
          align-items: center;
          justify-content: flex-start;
          height: 100%;
          padding: 0.5rem 0 0;
          border-bottom: none;
          gap: 0;
        }
        :host([collapsed]) .expanded      { display: none; }
        :host([collapsed]) .collapsed-view { display: flex; }
        :host([collapsed]) slot            { display: none; }
      </style>

      <button part="toggle" aria-label="Toggle navigation">
        <span class="expanded">
          <span class="icon">☰</span>
          <span>Navigation</span>
        </span>
        <span class="collapsed-view">
          <span class="chevron">›</span>
          <span class="label">Navigation</span>
        </span>
      </button>
      <slot></slot>
    `;

    shadow.querySelector('button').addEventListener('click', e => {
      e.stopPropagation();
      this.toggleAttribute('collapsed');
    });

    this.addEventListener('click', () => {
      if (this.hasAttribute('collapsed')) {
        this.removeAttribute('collapsed');
      }
    });
  }
}

if (!customElements.get('collapsable-side-bar')) {
  customElements.define('collapsable-side-bar', CollapsableSideBar);
}
