/**
 * Mini Gallery Web Component
 * Split-pane layout: image viewer on left, clickable file list on right
 * Accepts files in the same slot format as image-carousel
 *
 * Usage:
 * <mini-gallery preview-height="300">
 *   <img src="..." alt="...">
 *   <img src="..." data-filename="...">
 * </mini-gallery>
 */
class MiniGallery extends HTMLElement {
  static get observedAttributes() {
    return ["preview-height"];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    this.currentIndex = 0;
    this.items = [];
    this._fitMode = "contain";
    try {
      this._fitMode = localStorage.getItem("mini-gallery-fit-mode") || "contain";
    } catch (e) { /* localStorage unavailable */ }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          position: relative;
          width: 100%;
          max-width: calc(33.333% - 1rem);
          font-family: inherit;
          --primary-color: var(--bulma-link, #3e8ed0);
          --overlay-bg: rgba(18, 18, 18, 0.8);
          --overlay-text: #ffffff;
        }

        * {
          border-radius: 0 !important;
          box-sizing: border-box;
        }

        .gallery-container {
          display: flex;
          gap: 0;
          height: var(--gallery-height, 300px);
          border: 1px solid var(--bulma-border, #dbdbdb);
          background-color: var(--bulma-scheme-main-bis, #1e1e1e);
        }

        .image-pane {
          flex: 2;
          position: relative;
          overflow: hidden;
          display: flex;
          align-items: center;
          justify-content: center;
          background-color: var(--bulma-scheme-main-bis, #1e1e1e);
        }

        .image-container {
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
        }

        .image-container img {
          max-width: 100%;
          max-height: 100%;
          object-fit: var(--object-fit, contain);
        }

        .empty-state {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100%;
          height: 100%;
          color: var(--bulma-text-weak, #7a7a7a);
          font-size: 13px;
        }

        .file-list-pane {
          flex: 1;
          border-left: 1px solid var(--bulma-border, #dbdbdb);
          overflow-y: auto;
          display: flex;
          flex-direction: column;
        }

        .file-list {
          flex: 1;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
        }

        .file-item {
          padding: 0.75rem;
          border-bottom: 1px solid var(--bulma-border, #dbdbdb);
          cursor: pointer;
          transition: background-color 0.2s ease;
          user-select: none;
          flex-shrink: 0;
        }

        .file-item:hover {
          background-color: var(--bulma-scheme-main, #ffffff);
        }

        .file-item.active {
          background-color: var(--primary-color);
          color: white;
        }

        .file-item-name {
          font-size: 12px;
          font-weight: 500;
          margin: 0;
          word-break: break-word;
          line-height: 1.3;
        }

        .file-item-size {
          font-size: 11px;
          opacity: 0.7;
          margin: 0.25rem 0 0 0;
        }

        .settings-btn {
          position: absolute;
          top: 8px;
          right: 8px;
          background-color: var(--overlay-bg);
          border: 1px solid var(--bulma-border-weak, rgba(255, 255, 255, 0.1));
          color: var(--overlay-text);
          width: 36px;
          height: 36px;
          cursor: pointer;
          z-index: 10;
          opacity: 0;
          transition: opacity 0.3s ease, background-color 0.2s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0;
        }

        .image-pane:hover .settings-btn,
        .settings-btn.open {
          opacity: 1;
        }

        .settings-btn:hover {
          background-color: var(--primary-color);
        }

        .settings-btn svg {
          display: block;
        }

        .settings-menu {
          position: absolute;
          top: 48px;
          right: 8px;
          background-color: var(--overlay-bg);
          border: 1px solid var(--bulma-border-weak, rgba(255, 255, 255, 0.1));
          z-index: 11;
          display: none;
          flex-direction: column;
          min-width: 160px;
        }

        .settings-menu.open {
          display: flex;
        }

        .settings-option {
          background: none;
          border: none;
          color: var(--overlay-text);
          padding: 8px 12px;
          text-align: left;
          cursor: pointer;
          font-size: 13px;
          font-family: inherit;
          display: flex;
          align-items: center;
          gap: 8px;
          white-space: nowrap;
          transition: background-color 0.2s ease;
        }

        .settings-option:hover {
          background-color: rgba(255, 255, 255, 0.15);
        }

        .settings-option.active {
          color: var(--primary-color);
          font-weight: bold;
        }

        .settings-option .check {
          width: 14px;
          visibility: hidden;
        }

        .settings-option.active .check {
          visibility: visible;
        }

        .filename-display {
          position: absolute;
          top: 8px;
          left: 8px;
          background-color: var(--overlay-bg);
          border: 1px solid var(--bulma-border-weak, rgba(255, 255, 255, 0.1));
          color: var(--overlay-text);
          padding: 6px 10px;
          z-index: 10;
          opacity: 0;
          transition: opacity 0.3s ease;
          font-size: 12px;
          white-space: nowrap;
          text-overflow: ellipsis;
          max-width: 200px;
          overflow: hidden;
        }

        .image-pane:hover .filename-display {
          opacity: 1;
        }

        .filename-display a {
          color: var(--primary-color);
          text-decoration: none;
          cursor: pointer;
        }

        .filename-display a:hover {
          text-decoration: underline;
        }
      </style>
      <div class="gallery-container">
        <div class="image-pane">
          <div class="image-container" id="image-container"></div>
          <div class="filename-display" id="filename-display"></div>
          <button class="settings-btn" id="settings-btn" aria-label="Display settings" aria-haspopup="true" aria-expanded="false">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </button>
          <div class="settings-menu" id="settings-menu" role="menu">
            <button class="settings-option" data-fit="contain" role="menuitemradio"><span class="check">✓</span>Fit (whole image)</button>
            <button class="settings-option" data-fit="cover" role="menuitemradio"><span class="check">✓</span>Fill / crop</button>
            <button class="settings-option" data-fit="fill" role="menuitemradio"><span class="check">✓</span>Stretch</button>
          </div>
        </div>
        <div class="file-list-pane">
          <div class="file-list" id="file-list"></div>
        </div>
      </div>
      <slot style="display: none;"></slot>
    `;
  }

  connectedCallback() {
    this._updateDimensions();

    this.imageContainer = this.shadowRoot.querySelector('#image-container');
    this.fileListEl = this.shadowRoot.querySelector('#file-list');
    this.filenameDisplay = this.shadowRoot.querySelector('#filename-display');
    this.settingsBtn = this.shadowRoot.querySelector('#settings-btn');
    this.settingsMenu = this.shadowRoot.querySelector('#settings-menu');
    this.slotEl = this.shadowRoot.querySelector('slot');

    // Settings menu
    this.settingsBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this._toggleSettings();
    });
    this.settingsMenu.querySelectorAll('.settings-option').forEach((opt) => {
      opt.addEventListener('click', (e) => {
        e.stopPropagation();
        this._setFitMode(opt.getAttribute('data-fit'));
        this._toggleSettings(false);
      });
    });
    this.addEventListener('mousedown', (e) => {
      if (this.settingsMenu.classList.contains('open') &&
          !e.composedPath().includes(this.settingsMenu) &&
          !e.composedPath().includes(this.settingsBtn)) {
        this._toggleSettings(false);
      }
    });

    // Handle slot changes
    const onSlotChange = () => {
      this.items = this.slotEl.assignedElements();
      this._applyFitMode();
      this._renderFileList();
      this._renderImage(0);
    };

    this.slotEl.addEventListener('slotchange', onSlotChange);
    onSlotChange();

    this._observer = new MutationObserver(onSlotChange);
    this._observer.observe(this, { childList: true, subtree: true });
  }

  disconnectedCallback() {
    if (this._observer) {
      this._observer.disconnect();
    }
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue) return;
    if (name === "preview-height") {
      this._updateDimensions();
    }
  }

  _updateDimensions() {
    const height = this.getAttribute("preview-height") || "300";
    const formattedHeight = height.endsWith("px") || height.endsWith("%") || height.endsWith("vh")
      ? height
      : `${height}px`;
    this.shadowRoot.querySelector('.gallery-container').style.setProperty("--gallery-height", formattedHeight);
  }

  _toggleSettings(force) {
    const open = force === undefined ? !this.settingsMenu.classList.contains('open') : force;
    this.settingsMenu.classList.toggle('open', open);
    this.settingsBtn.classList.toggle('open', open);
    this.settingsBtn.setAttribute('aria-expanded', String(open));
  }

  _setFitMode(mode) {
    if (!["contain", "cover", "fill"].includes(mode)) return;
    this._fitMode = mode;
    try {
      localStorage.setItem("mini-gallery-fit-mode", mode);
    } catch (e) { /* localStorage unavailable */ }
    this._applyFitMode();
  }

  _applyFitMode() {
    const objectFitValue = this._fitMode === 'fill' ? 'fill' : this._fitMode;
    this.imageContainer.style.setProperty("--object-fit", objectFitValue);

    if (this.settingsMenu) {
      this.settingsMenu.querySelectorAll('.settings-option').forEach((opt) => {
        opt.classList.toggle('active', opt.getAttribute('data-fit') === this._fitMode);
      });
    }
  }

  _renderFileList() {
    this.fileListEl.innerHTML = '';

    if (!this.items || this.items.length === 0) {
      this.fileListEl.innerHTML = '<div class="file-item"><p class="file-item-name has-text-grey is-size-7">None.</p></div>';
      return;
    }

    this.items.forEach((item, index) => {
      const div = document.createElement('div');
      div.className = 'file-item';
      if (index === this.currentIndex) {
        div.classList.add('active');
      }

      let filename = null;
      if (item.tagName === 'IMG') {
        filename = item.getAttribute('alt') ||
                  item.getAttribute('title') ||
                  item.getAttribute('data-filename');
        if (!filename) {
          try {
            const url = new URL(item.src, window.location.origin);
            filename = url.pathname.split('/').filter(Boolean).pop();
          } catch (e) {
            filename = item.src.split('/').filter(Boolean).pop();
          }
        }
      } else if (item.hasAttribute('data-filename')) {
        filename = item.getAttribute('data-filename');
      }

      filename = filename?.split('?')[0] || `Item ${index + 1}`;

      const nameEl = document.createElement('p');
      nameEl.className = 'file-item-name';
      nameEl.textContent = filename;
      div.appendChild(nameEl);

      if (item.hasAttribute('data-size')) {
        const sizeEl = document.createElement('p');
        sizeEl.className = 'file-item-size';
        sizeEl.textContent = item.getAttribute('data-size');
        div.appendChild(sizeEl);
      }

      div.addEventListener('click', () => this._selectFile(index));
      this.fileListEl.appendChild(div);
    });
  }

  _selectFile(index) {
    this.currentIndex = index;
    this._renderFileList();
    this._renderImage(index);
    this.dispatchEvent(new CustomEvent("mini-gallery-change", { detail: { index } }));
  }

  _renderImage(index) {
    this.imageContainer.innerHTML = '';

    if (!this.items || this.items.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = 'No images';
      this.imageContainer.appendChild(empty);
      this.filenameDisplay.innerHTML = '';
      return;
    }

    const item = this.items[index];
    if (!item) return;

    if (item.tagName === 'IMG') {
      const img = document.createElement('img');
      img.src = item.src;
      img.alt = item.getAttribute('alt') || '';
      this.imageContainer.appendChild(img);
      this._updateFilenameDisplay(item);
    } else if (item.hasAttribute('data-filename')) {
      const div = document.createElement('div');
      div.className = 'empty-state';
      div.textContent = item.getAttribute('data-filename');
      this.imageContainer.appendChild(div);
      this.filenameDisplay.innerHTML = '';
    }
  }

  _updateFilenameDisplay(imgElement) {
    let filename = imgElement.getAttribute('alt') ||
                  imgElement.getAttribute('title') ||
                  imgElement.getAttribute('data-filename');

    if (!filename) {
      try {
        const url = new URL(imgElement.src, window.location.origin);
        filename = url.pathname.split('/').filter(Boolean).pop();
      } catch (e) {
        filename = imgElement.src.split('/').filter(Boolean).pop();
      }
    }

    filename = filename?.split('?')[0] || null;

    if (filename && imgElement.src) {
      this.filenameDisplay.innerHTML = `<a href="${imgElement.src}" download="${filename}" title="${filename}">${filename}</a>`;
    } else {
      this.filenameDisplay.innerHTML = '';
    }
  }
}

if (!customElements.get("mini-gallery")) {
  customElements.define("mini-gallery", MiniGallery);
}
