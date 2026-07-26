---
type: Architecture Example
title: HTMX CSRF and Search Snippets
description: Concrete markup for the project's HTMX CSRF token hook and search patterns.
tags: [architecture, htmx, frontend, csrf, examples]
---

# HTMX CSRF and search snippets

Concrete markup for the patterns in [../patterns/htmx_patterns.md](../patterns/htmx_patterns.md).

## Base template — CSRF token hook

Include once in the project base template (for example `templates/base.html`) so every HTMX request sends the CSRF token header.

```html
<script>
    document.body.addEventListener('htmx:configRequest', (event) => {
        event.detail.headers['X-CSRFToken'] = '{{ csrf_token }}';
    });
</script>
```

Rely on `django.template.context_processors.csrf` (default with the Django template backend) so `{{ csrf_token }}` resolves in templates.

## Search input — fragment-only response

Same canonical list URL plus `format=htmx-search-results&q=...`. The view branches on `format` and returns only the results fragment (e.g. `_results_list.html`).

```html
<input type="text" name="q"
       hx-get="{% url 'comment-search' %}?format=htmx-search-results"
       hx-trigger="keyup changed delay:500ms, search"
       hx-target="#search-results-container"
       hx-push-url="true"
       hx-indicator=".search-skeleton">
```

## Skeleton indicator wrapper

```html
<div id="event-card-container" class="is-relative">
    <div class="htmx-indicator">
        <div class="skeleton-block" style="width: 100%; height: 200px;"></div>
        <div class="skeleton-lines">
            <div></div><div></div><div></div>
        </div>
    </div>

    <div class="htmx-content-wrapper">
         <button hx-get="/events/1/"
                 hx-target="#event-card-container"
                 hx-select="#event-card-content"
                 hx-indicator=".htmx-indicator">
             Refresh Details
         </button>
         <div id="event-card-content">
             …
         </div>
    </div>
</div>
```
