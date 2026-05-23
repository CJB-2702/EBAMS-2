/**
 * <toast-alert> — dismissible toast notification, fixed-position, auto-dismiss.
 *
 * Design intent
 * -------------
 * Standalone toast component that spans the main content width, positioned
 * fixed at top-center. Auto-dismisses after a configurable delay. Click
 * the .delete button to dismiss early. No Shadow DOM (markup is light-DOM,
 * so callers can inspect/style if needed).
 *
 * Usage (hardcoded)
 *   <toast-alert type="success" dismiss-delay="3000">
 *     Operation completed successfully.
 *   </toast-alert>
 *
 * Usage (HTMX response)
 *   <!-- Server returns this as the first element in the response -->
 *   <toast-alert type="success" dismiss-delay="3000">
 *     Permissions updated.
 *   </toast-alert>
 *   <dual-list-box id="up-perms-dlb">…</dual-list-box>
 *
 * Attributes
 *   type           "success" | "danger" | "warning" | "info" (default: "info")
 *   dismiss-delay  milliseconds before auto-dismiss (default: 3000)
 *                  Set to 0 to disable auto-dismiss; user must click .delete
 *
 * Public API
 *   el.dismiss()   Remove the alert immediately
 *
 * Events (bubble, composed)
 *   toast-alert-dismiss   when the alert is dismissed (either auto or manual)
 *
 * CSS Requirements (add once globally or per-page)
 *   toast-alert {
 *     --toast-max-width: <your content width, e.g. 1216px>;
 *     --toast-top-offset: 2rem;
 *   }
 *
 * Styling
 *   Inherits Bulma notification classes (is-success, is-danger, etc).
 *   Uses CSS custom properties for width/position if --toast-max-width is set.
 *   Falls back to 100% width and padding if not set (mobile-friendly).
 */
(function () {
  if (!document.getElementById('toast-alert-styles')) {
    const style = document.createElement('style');
    style.id = 'toast-alert-styles';
    style.textContent = `
      toast-alert {
        position: fixed !important;
        top: var(--toast-top-offset, 2rem) !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 10000 !important;
        max-width: var(--toast-max-width, 100%) !important;
        width: calc(100% - 2rem) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
        animation: toast-alert-slide-down 0.3s ease-out !important;
        margin: 0 !important;
        padding: 1.25rem 2.5rem 1.25rem 1.5rem !important;
        border-radius: 4px !important;
      }
      @keyframes toast-alert-slide-down {
        from {
          opacity: 0;
          transform: translateX(-50%) translateY(-1rem);
        }
        to {
          opacity: 1;
          transform: translateX(-50%) translateY(0);
        }
      }
      toast-alert .delete {
        cursor: pointer;
      }
    `;
    document.head.appendChild(style);
  }

  class ToastAlert extends HTMLElement {
    connectedCallback() {
      if (this._ready) return;

      this._type = this.getAttribute('type') || 'info';
      this._delay = parseInt(this.getAttribute('dismiss-delay'), 10) || 3000;

      // Ensure toast is attached to body (not a positioned ancestor).
      // HTMX swaps may insert the toast inside a div that will be replaced.
      // Move it to body so fixed positioning works correctly.
      if (this.parentElement && this.parentElement !== document.body) {
        const content = this.innerHTML;
        const type = this.getAttribute('type');
        const delay = this.getAttribute('dismiss-delay');

        const newAlert = document.createElement('toast-alert');
        newAlert.setAttribute('type', type);
        newAlert.setAttribute('dismiss-delay', delay);
        newAlert.setAttribute('data-rerouted', 'true');
        newAlert.innerHTML = content;
        document.body.appendChild(newAlert);
        this.remove();
        return;
      }

      this._ready = true;

      // Apply Bulma notification class.
      this.className = `notification is-${this._type} is-light`;

      // Wrap content in a container (preserve user text content).
      const content = document.createElement('div');
      content.className = 'toast-alert-content';
      [...this.childNodes].forEach(node => content.appendChild(node));

      // Build delete button.
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'delete';
      deleteBtn.setAttribute('aria-label', 'Dismiss notification');
      deleteBtn.type = 'button';

      // Assemble: button first (right side), then content.
      this.appendChild(deleteBtn);
      this.insertBefore(content, deleteBtn);

      this._deleteBtn = deleteBtn;
      this._bind();

      // Auto-dismiss if delay > 0.
      if (this._delay > 0) {
        this._dismissTimer = setTimeout(() => this.dismiss(), this._delay);
      }
    }

    dismiss() {
      if (this._dismissTimer) clearTimeout(this._dismissTimer);
      this.dispatchEvent(new CustomEvent('toast-alert-dismiss', {
        bubbles: true,
        composed: true,
      }));
      this.remove();
    }

    _bind() {
      this._deleteBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.dismiss();
      });
    }
  }

  if (!customElements.get('toast-alert')) {
    customElements.define('toast-alert', ToastAlert);
  }
})();
