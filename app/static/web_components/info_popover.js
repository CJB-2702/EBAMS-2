/**
 * <info-popover> — small hover/click info bubble, positioned relative to a trigger.
 *
 * Design intent
 * -------------
 * Native `popover="auto"` + `popovertarget` was unreliable for this (anchoring
 * inside scroll/overflow containers, no hover trigger, inconsistent placement).
 * This component reimplements the same "hover over item for info" pattern by
 * hand: it detaches its content box to <body> and positions it with
 * getBoundingClientRect(), so it is never clipped by an ancestor's overflow
 * and never fights the anchor-positioning browser support matrix.
 *
 * Markup uses <detail>/<summary> child tags (not the native <details>/<summary>
 * elements — this is deliberate for the semantic naming, not an accordion).
 *   <detail>   the trigger — an icon or short anchor-style text
 *   <summary>  the popover body content
 *
 * Usage
 *   <info-popover direction="top" hover="true">
 *     <detail><span class="icon has-text-info"><span class="material-icons" aria-hidden="true">help_outline</span></span></detail>
 *     <summary>
 *       <p>Explanatory text…</p>
 *     </summary>
 *   </info-popover>
 *
 * Attributes
 *   direction   "top" | "bottom" | "left" | "right" (default: "top")
 *   hover       "true" (default) shows on hover/focus; "false" shows on click
 *               and closes on outside click / Escape.
 *
 * Accessibility
 *   Trigger is a real <button> (focusable, keyboard-activatable). Content box
 *   has role="tooltip"/"dialog" as appropriate and is linked via
 *   aria-describedby. Focus shows the popover in hover mode too, so keyboard
 *   users get the same info as mouse users.
 */
(function () {
  if (!document.getElementById('info-popover-styles')) {
    const style = document.createElement('style');
    style.id = 'info-popover-styles';
    style.textContent = `
      info-popover { display: inline-flex; align-items: center; }
      .info-popover-trigger {
        background: none; border: none; padding: 0; margin: 0;
        cursor: pointer; display: inline-flex; align-items: center;
        color: var(--bulma-info, #3e8ed0); font: inherit;
      }
      .info-popover-trigger--text {
        text-decoration: underline dotted;
        text-underline-offset: 2px;
        font-size: 0.85em;
      }
      .info-popover-content {
        position: fixed;
        z-index: 10000;
        max-width: 22rem;
        background: var(--bulma-scheme-main, #fff);
        border: 1px solid var(--bulma-border-weak, #dbdbdb);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        padding: 0.75rem;
        font-size: 0.8rem;
        line-height: 1.4;
        border-radius: 0;
        opacity: 0;
        visibility: hidden;
        transform: translateY(2px);
        transition: opacity 0.12s ease, transform 0.12s ease;
      }
      .info-popover-content.is-open {
        opacity: 1;
        visibility: visible;
        transform: translateY(0);
      }
      .info-popover-content > *:last-child { margin-bottom: 0 !important; }
    `;
    document.head.appendChild(style);
  }

  const DIRECTIONS = ['top', 'bottom', 'left', 'right'];
  const GAP = 8;
  let uid = 0;

  class InfoPopover extends HTMLElement {
    connectedCallback() {
      if (this._mounted) return;
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => this._tryInit(), { once: true });
      } else {
        this._tryInit();
      }
    }

    disconnectedCallback() {
      this._observer?.disconnect();
    }

    _tryInit() {
      if (this._mounted) return;
      this._mounted = true;

      if (!this._observer) {
        this._observer = new MutationObserver(() => this._tryInit());
        this._observer.observe(this, { childList: true, subtree: true });
      }

      this._init();
    }

    _init() {
      this._id = `info-popover-${++uid}`;
      this._direction = DIRECTIONS.includes(this.getAttribute('direction'))
        ? this.getAttribute('direction')
        : 'top';
      this._hoverMode = this.getAttribute('hover') !== 'false';

      const detailEl = this.querySelector('detail');
      const summaryEl = this.querySelector('summary');

      const triggerHTML = detailEl ? detailEl.innerHTML : '';
      const contentHTML = summaryEl ? summaryEl.innerHTML : '';
      const isIconTrigger = !!(detailEl && detailEl.querySelector('.material-icons, svg, img'));

      this.innerHTML = '';

      const trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.className = 'info-popover-trigger' + (isIconTrigger ? '' : ' info-popover-trigger--text');
      trigger.innerHTML = triggerHTML;
      trigger.setAttribute('aria-describedby', this._id);
      this.appendChild(trigger);

      const content = document.createElement('div');
      content.id = this._id;
      content.className = 'info-popover-content';
      content.setAttribute('role', this._hoverMode ? 'tooltip' : 'dialog');
      content.innerHTML = contentHTML;
      document.body.appendChild(content);

      this._trigger = trigger;
      this._content = content;
      this._open = false;

      this._bind();
    }

    disconnectedCallback() {
      if (this._content) this._content.remove();
    }

    show() {
      if (this._open) return;
      this._open = true;
      this._position();
      this._content.classList.add('is-open');
      if (!this._hoverMode) {
        document.addEventListener('click', this._onDocumentClick, true);
        document.addEventListener('keydown', this._onKeydown, true);
      }
    }

    hide() {
      if (!this._open) return;
      this._open = false;
      this._content.classList.remove('is-open');
      document.removeEventListener('click', this._onDocumentClick, true);
      document.removeEventListener('keydown', this._onKeydown, true);
    }

    _position() {
      const triggerRect = this._trigger.getBoundingClientRect();
      const contentRect = this._content.getBoundingClientRect();
      const viewportW = window.innerWidth;
      const viewportH = window.innerHeight;

      let direction = this._direction;
      if (direction === 'top' && triggerRect.top - contentRect.height - GAP < 0) direction = 'bottom';
      if (direction === 'bottom' && triggerRect.bottom + contentRect.height + GAP > viewportH) direction = 'top';
      if (direction === 'left' && triggerRect.left - contentRect.width - GAP < 0) direction = 'right';
      if (direction === 'right' && triggerRect.right + contentRect.width + GAP > viewportW) direction = 'left';

      let top, left;
      switch (direction) {
        case 'bottom':
          top = triggerRect.bottom + GAP;
          left = triggerRect.left + triggerRect.width / 2 - contentRect.width / 2;
          break;
        case 'left':
          top = triggerRect.top + triggerRect.height / 2 - contentRect.height / 2;
          left = triggerRect.left - contentRect.width - GAP;
          break;
        case 'right':
          top = triggerRect.top + triggerRect.height / 2 - contentRect.height / 2;
          left = triggerRect.right + GAP;
          break;
        case 'top':
        default:
          top = triggerRect.top - contentRect.height - GAP;
          left = triggerRect.left + triggerRect.width / 2 - contentRect.width / 2;
          break;
      }

      left = Math.max(GAP, Math.min(left, viewportW - contentRect.width - GAP));
      top = Math.max(GAP, Math.min(top, viewportH - contentRect.height - GAP));

      this._content.style.top = `${top}px`;
      this._content.style.left = `${left}px`;
    }

    _bind() {
      this._onDocumentClick = (e) => {
        if (!this._content.contains(e.target) && !this._trigger.contains(e.target)) this.hide();
      };
      this._onKeydown = (e) => {
        if (e.key === 'Escape') this.hide();
      };

      if (this._hoverMode) {
        const scheduleHide = () => {
          this._hideTimer = setTimeout(() => this.hide(), 120);
        };
        const cancelHide = () => {
          if (this._hideTimer) clearTimeout(this._hideTimer);
        };

        this._trigger.addEventListener('mouseenter', () => { cancelHide(); this.show(); });
        this._trigger.addEventListener('mouseleave', scheduleHide);
        this._content.addEventListener('mouseenter', cancelHide);
        this._content.addEventListener('mouseleave', scheduleHide);
        this._trigger.addEventListener('focus', () => this.show());
        this._trigger.addEventListener('blur', () => this.hide());
      } else {
        this._trigger.addEventListener('click', (e) => {
          e.stopPropagation();
          this._open ? this.hide() : this.show();
        });
      }

      window.addEventListener('scroll', () => { if (this._open) this._position(); }, true);
      window.addEventListener('resize', () => { if (this._open) this._position(); });
    }
  }

  if (!customElements.get('info-popover')) {
    customElements.define('info-popover', InfoPopover);
  }
})();
