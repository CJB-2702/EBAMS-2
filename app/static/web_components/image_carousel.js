/**
 * Modern Image & Content Carousel Web Component (gesture-enabled sliding track)
 * Accepts arbitrary slides via slots and provides touch swipe / mouse drag gestures,
 * loops, autoplay, side overlays, and focus-aware keyboard navigation.
 *
 * Usage:
 * <image-carousel preview-height="300" loop autoplay autoplay-delay="4000">
 *   <div>Arbitrary Content</div>
 *   <img src="...">
 * </image-carousel>
 */
class ImageCarousel extends HTMLElement {
  static get observedAttributes() {
    return ["autoplay", "autoplay-delay", "loop", "preview-height"];
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    
    this.currentIndex = 0;
    this.items = [];
    this.isDragging = false;
    this.startX = 0;
    this.currentTranslate = 0;
    this.prevTranslate = 0;
    this.autoplayTimer = null;
    this._isPaused = false;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          position: relative;
          width: 100%;
          overflow: hidden;
          font-family: inherit;
          --primary-color: var(--bulma-link, #3e8ed0);
          --overlay-bg: rgba(18, 18, 18, 0.8);
          --overlay-text: #ffffff;
          outline: none;
        }

        /* All elements must use sharp corners */
        * {
          border-radius: 0 !important;
        }

        .carousel-viewer {
          position: relative;
          overflow: hidden;
          width: 100%;
          height: var(--carousel-height, 300px);
          background-color: var(--bulma-scheme-main-bis, #1e1e1e);
          border: 1px solid var(--bulma-border, #dbdbdb);
        }
        
        .carousel-track {
          display: flex;
          height: 100%;
          width: 100%;
          transition: transform 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
          will-change: transform;
          cursor: grab;
          user-select: none;
        }

        .carousel-track.dragging {
          cursor: grabbing;
          transition: none !important;
        }
        
        ::slotted(*) {
          flex: 0 0 100%;
          width: 100%;
          max-width: 100%;
          height: 100%;
          box-sizing: border-box;
          display: block;
          user-select: none;
        }

        /* Overlay Controls */
        .nav-btn {
          position: absolute;
          top: 50%;
          transform: translateY(-50%);
          background-color: var(--overlay-bg);
          border: 1px solid var(--bulma-border-weak, rgba(255, 255, 255, 0.1));
          color: var(--overlay-text);
          width: 44px;
          height: 44px;
          cursor: pointer;
          z-index: 10;
          opacity: 0;
          transition: opacity 0.3s ease, background-color 0.2s ease, transform 0.2s ease;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .carousel-viewer:hover .nav-btn {
          opacity: 1;
        }

        .nav-btn:hover {
          background-color: var(--primary-color);
          transform: translateY(-50%) scale(1.05);
        }

        .nav-btn:active {
          transform: translateY(-50%) scale(0.95);
        }

        .prev-btn { left: 0; }
        .next-btn { right: 0; }

        .nav-btn svg {
          display: block;
        }

        /* Indicators: dash lines that morph / stretch */
        .indicators {
          position: absolute;
          bottom: 15px;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          gap: 6px;
          z-index: 12;
        }

        .indicator {
          width: 8px;
          height: 4px;
          background: rgba(255, 255, 255, 0.4);
          cursor: pointer;
          border: none;
          padding: 0;
          transition: width 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                      background-color 0.3s ease;
        }

        .indicator:hover {
          background: rgba(255, 255, 255, 0.8);
        }

        .indicator.active {
          width: 24px;
          background: var(--primary-color);
        }

        /* Simple focus ring on host */
        :host(:focus-visible) .carousel-viewer {
          outline: 2px solid var(--primary-color);
        }
      </style>
      <div class="carousel-viewer" tabindex="0">
        <div class="carousel-track">
          <slot></slot>
        </div>
        <button class="nav-btn prev-btn" id="prev" aria-label="Previous">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="square" stroke-linejoin="miter">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>
        <button class="nav-btn next-btn" id="next" aria-label="Next">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="square" stroke-linejoin="miter">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>
        <div class="indicators" id="indicators"></div>
      </div>
    `;
  }

  connectedCallback() {
    this.viewer = this.shadowRoot.querySelector('.carousel-viewer');
    this.track = this.shadowRoot.querySelector('.carousel-track');
    this.prevBtn = this.shadowRoot.querySelector('#prev');
    this.nextBtn = this.shadowRoot.querySelector('#next');
    this.indicatorsContainer = this.shadowRoot.querySelector('#indicators');
    this.slotEl = this.shadowRoot.querySelector('slot');

    this._updateDimensions();

    this.prevBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.prev();
    });
    this.nextBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.next();
    });

    // Handle slot changes
    const onSlotChange = () => {
      this.items = this.slotEl.assignedElements();
      // Ensure all slotted elements have flex item styling
      this.items.forEach(el => {
        el.style.flex = "0 0 100%";
        el.style.width = "100%";
        el.style.maxWidth = "100%";
        el.style.height = "100%";
        el.style.boxSizing = "border-box";
      });
      this.renderIndicators();
      this.updateCarousel();
      this._startAutoplay();

      // Dispatch items change event so connected previews sync instantly
      this.dispatchEvent(new CustomEvent("carousel-items-changed", { detail: { items: this.items } }));
    };
    
    this.slotEl.addEventListener('slotchange', onSlotChange);
    onSlotChange();

    this._observer = new MutationObserver(onSlotChange);
    this._observer.observe(this, { childList: true, subtree: true });

    // Keyboard controls
    this.viewer.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') {
        this.prev();
      } else if (e.key === 'ArrowRight') {
        this.next();
      }
    });

    // Touch and Mouse Drag bindings
    this.viewer.addEventListener('touchstart', (e) => this._startDrag(e), { passive: true });
    this.viewer.addEventListener('touchmove', (e) => this._drag(e), { passive: true });
    this.viewer.addEventListener('touchend', () => this._endDrag());

    this.viewer.addEventListener('mousedown', (e) => this._startDrag(e));
    this.viewer.addEventListener('mousemove', (e) => this._drag(e));
    this.viewer.addEventListener('mouseup', () => this._endDrag());
    this.viewer.addEventListener('mouseleave', () => {
      if (this.isDragging) this._endDrag();
    });

    // Pause autoplay on mouse hover
    this.viewer.addEventListener('mouseenter', () => {
      this._isPaused = true;
      this._stopAutoplayTimer();
    });
    this.viewer.addEventListener('mouseleave', () => {
      this._isPaused = false;
      this._startAutoplay();
    });
  }

  disconnectedCallback() {
    this._stopAutoplayTimer();
    if (this._observer) {
      this._observer.disconnect();
    }
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue) return;
    if (name === "autoplay" || name === "autoplay-delay") {
      this._startAutoplay();
    } else if (name === "preview-height") {
      this._updateDimensions();
    }
  }

  _updateDimensions() {
    const height = this.getAttribute("preview-height") || "300";
    const viewer = this.shadowRoot.querySelector('.carousel-viewer');
    if (!viewer) return;
    const formattedHeight = height.endsWith("px") || height.endsWith("%") || height.endsWith("vh") ? height : `${height}px`;
    viewer.style.setProperty("--carousel-height", formattedHeight);
  }

  renderIndicators() {
    this.indicatorsContainer.innerHTML = '';
    if (this.items && this.items.length > 1) {
      this.items.forEach((_, index) => {
        const dot = document.createElement('button');
        dot.classList.add('indicator');
        if (index === this.currentIndex) dot.classList.add('active');
        dot.setAttribute('aria-label', `Go to slide ${index + 1}`);
        dot.addEventListener('click', (e) => {
          e.stopPropagation();
          this.goTo(index);
        });
        this.indicatorsContainer.appendChild(dot);
      });
    }
  }

  next() {
    if (this.items && this.items.length > 0) {
      const loop = this.hasAttribute("loop") || this.getAttribute("loop") !== "false";
      if (this.currentIndex < this.items.length - 1) {
        this.goTo(this.currentIndex + 1);
      } else if (loop) {
        this.goTo(0);
      }
    }
  }

  prev() {
    if (this.items && this.items.length > 0) {
      const loop = this.hasAttribute("loop") || this.getAttribute("loop") !== "false";
      if (this.currentIndex > 0) {
        this.goTo(this.currentIndex - 1);
      } else if (loop) {
        this.goTo(this.items.length - 1);
      }
    }
  }

  goTo(index) {
    if (index >= 0 && index < this.items.length) {
      this.currentIndex = index;
      this.updateCarousel();
      this._startAutoplay();
      this.dispatchEvent(new CustomEvent("carousel-change", { detail: { index: this.currentIndex } }));
    }
  }

  updateCarousel() {
    if (this.items && this.items.length > 0) {
      const width = this.getBoundingClientRect().width;
      this.currentTranslate = -this.currentIndex * width;
      this.prevTranslate = this.currentTranslate;
      this.track.style.transform = `translateX(${this.currentTranslate}px)`;
      
      const dots = this.indicatorsContainer.querySelectorAll('.indicator');
      dots.forEach((dot, index) => {
        if (index === this.currentIndex) {
          dot.classList.add('active');
        } else {
          dot.classList.remove('active');
        }
      });
    }
  }

  /* Swipe & Drag Physics */
  _startDrag(e) {
    if (this.items.length <= 1) return;
    this.isDragging = true;
    this.track.classList.add('dragging');
    this._stopAutoplayTimer();

    this.startX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
    const width = this.getBoundingClientRect().width;
    this.prevTranslate = -this.currentIndex * width;
  }

  _drag(e) {
    if (!this.isDragging) return;
    const currentX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
    const diff = currentX - this.startX;
    
    // Bounds calculations with rubber banding resistance
    const width = this.getBoundingClientRect().width;
    const maxTranslate = 0;
    const minTranslate = -(this.items.length - 1) * width;
    
    let translate = this.prevTranslate + diff;
    if (translate > maxTranslate) {
      translate = maxTranslate + (translate - maxTranslate) * 0.3; // Resistance
    } else if (translate < minTranslate) {
      translate = minTranslate + (translate - minTranslate) * 0.3; // Resistance
    }
    
    this.currentTranslate = translate;
    this.track.style.transform = `translateX(${this.currentTranslate}px)`;
  }

  _endDrag() {
    if (!this.isDragging) return;
    this.isDragging = false;
    this.track.classList.remove('dragging');

    const width = this.getBoundingClientRect().width;
    const movedBy = this.currentTranslate - this.prevTranslate;
    
    // Snapping thresholds: if dragged > 15% of container width, move to next/prev
    const threshold = width * 0.15;
    
    if (movedBy < -threshold && this.currentIndex < this.items.length - 1) {
      this.currentIndex++;
    } else if (movedBy > threshold && this.currentIndex > 0) {
      this.currentIndex--;
    }
    
    this.updateCarousel();
    this.dispatchEvent(new CustomEvent("carousel-change", { detail: { index: this.currentIndex } }));
    this._startAutoplay();
  }

  /* Autoplay logic */
  _startAutoplay() {
    this._stopAutoplayTimer();
    if (!this.hasAttribute("autoplay") || this._isPaused) return;

    const delay = parseInt(this.getAttribute("autoplay-delay")) || 4000;
    this.autoplayTimer = setTimeout(() => {
      this.next();
    }, delay);
  }

  _stopAutoplayTimer() {
    if (this.autoplayTimer) {
      clearTimeout(this.autoplayTimer);
      this.autoplayTimer = null;
    }
  }
}

if (!customElements.get("image-carousel")) {
  customElements.define("image-carousel", ImageCarousel);
}


/**
 * CarouselPreviewItems Component
 * Connects to <image-carousel> to display a row of size-configurable items.
 *
 * Usage:
 * <carousel-preview-items for="carousel-id" size="50"></carousel-preview-items>
 */
class CarouselPreviewItems extends HTMLElement {
  static get observedAttributes() {
    return ["for", "size"];
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._carousel = null;
    this._size = 50;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: flex;
          gap: 0.5rem;
          flex-wrap: wrap;
          margin-top: 0.75rem;
          justify-content: center;
          width: 100%;
        }
        * {
          border-radius: 0 !important;
          box-sizing: border-box;
        }
        .preview-item {
          width: var(--preview-size, 50px);
          height: var(--preview-size, 50px);
          border: 1px solid var(--bulma-border, #dbdbdb);
          background-color: var(--bulma-scheme-main-bis, #1e1e1e);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          transition: border-color 0.2s ease, opacity 0.2s ease, transform 0.2s ease;
          opacity: 0.5;
          user-select: none;
        }
        .preview-item:hover {
          opacity: 1;
          transform: scale(1.05);
        }
        .preview-item.active {
          opacity: 1;
          border: 2px solid var(--primary-color, var(--bulma-link, #3e8ed0));
        }
        .preview-item img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
        .preview-item svg {
          width: 50%;
          height: 50%;
          stroke: currentColor;
          fill: none;
          stroke-width: 2.5;
          display: block;
        }
        .preview-number {
          font-family: var(--app-font-mono-input, monospace);
          font-weight: bold;
          font-size: calc(var(--preview-size, 50px) * 0.35);
          color: var(--bulma-text, #4a4a4a);
        }
        .preview-item.active .preview-number {
          color: var(--primary-color, var(--bulma-link, #3e8ed0));
        }
      </style>
      <!-- Preview items container -->
    `;
  }

  connectedCallback() {
    this._updateSize();
    this._connectToCarousel();
  }

  disconnectedCallback() {
    this._disconnectFromCarousel();
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue) return;
    if (name === "size") {
      this._updateSize();
    } else if (name === "for") {
      this._connectToCarousel();
    }
  }

  _updateSize() {
    const size = this.getAttribute("size") || "50";
    this._size = parseInt(size) || 50;
    this.style.setProperty("--preview-size", `${this._size}px`);
  }

  _connectToCarousel() {
    this._disconnectFromCarousel();

    const targetId = this.getAttribute("for");
    if (!targetId) return;

    const root = this.getRootNode();
    const carousel = root.getElementById(targetId) || document.getElementById(targetId);
    if (!carousel) {
      // Retry in a moment if not ready in the DOM
      setTimeout(() => this._connectToCarousel(), 100);
      return;
    }

    this._carousel = carousel;

    this._onItemsChanged = (e) => {
      this._renderPreviews(e.detail.items);
    };
    this._onIndexChanged = (e) => {
      this._setActive(e.detail.index);
    };

    this._carousel.addEventListener("carousel-items-changed", this._onItemsChanged);
    this._carousel.addEventListener("carousel-change", this._onIndexChanged);

    // Initial Render
    if (this._carousel.items) {
      this._renderPreviews(this._carousel.items);
      this._setActive(this._carousel.currentIndex || 0);
    }
  }

  _disconnectFromCarousel() {
    if (this._carousel) {
      if (this._onItemsChanged) {
        this._carousel.removeEventListener("carousel-items-changed", this._onItemsChanged);
      }
      if (this._onIndexChanged) {
        this._carousel.removeEventListener("carousel-change", this._onIndexChanged);
      }
      this._carousel = null;
    }
  }

  _renderPreviews(items) {
    const shadow = this.shadowRoot;
    const oldItems = shadow.querySelectorAll(".preview-item");
    oldItems.forEach(el => el.remove());

    if (!items || items.length === 0) return;

    items.forEach((item, index) => {
      const btn = document.createElement("div");
      btn.className = "preview-item";
      btn.setAttribute("role", "button");
      btn.setAttribute("aria-label", `Jump to slide ${index + 1}`);

      if (item.tagName === "IMG") {
        const img = document.createElement("img");
        img.src = item.src;
        img.alt = item.alt || "";
        btn.appendChild(img);
      } else if (item.hasAttribute("data-preview-icon")) {
        const iconName = item.getAttribute("data-preview-icon");
        btn.innerHTML = this._getIconSvg(iconName);
      } else {
        const num = document.createElement("span");
        num.className = "preview-number";
        num.textContent = String(index + 1).padStart(2, "0");
        btn.appendChild(num);
      }

      btn.addEventListener("click", () => {
        if (this._carousel) {
          this._carousel.goTo(index);
        }
      });

      shadow.appendChild(btn);
    });

    if (this._carousel) {
      this._setActive(this._carousel.currentIndex || 0);
    }
  }

  _setActive(activeIndex) {
    const items = this.shadowRoot.querySelectorAll(".preview-item");
    items.forEach((item, index) => {
      if (index === activeIndex) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });
  }

  _getIconSvg(name) {
    const icons = {
      cloud: `<svg viewBox="0 0 24 24"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>`,
      database: `<svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v6c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 11v6c0 1.66 4 3 9 3s9-1.34 9-3v-6"/></svg>`,
      lock: `<svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`,
      image: `<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
      settings: `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`
    };
    return icons[name] || icons.image;
  }
}

if (!customElements.get("carousel-preview-items")) {
  customElements.define("carousel-preview-items", CarouselPreviewItems);
}
