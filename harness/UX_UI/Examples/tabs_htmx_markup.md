---
type: "UX Example"
title: "HTMX tabs markup"
description: "Canonical markup for Approach 1 (HTMX tabs) in [../components/tabs.md](../components/tabs.md)."
tags: [ux-ui, ux-example, examples]
context_tier: 3
---

# HTMX tabs markup

Canonical markup for Approach 1 (HTMX tabs) in [../components/tabs.md](../components/tabs.md).

```html
<div class="tabs">
  <ul>
    <li class="is-active"
        hx-get="/administration/users/2/edit?view=information"
        hx-target="#tabs-content"
        hx-push-url="true">
      <a>Information</a>
    </li>
    <li hx-get="/administration/users/2/edit?view=permissions"
        hx-target="#tabs-content"
        hx-push-url="true">
      <a>Permissions</a>
    </li>
    <li hx-get="/administration/users/2/edit?view=data-access"
        hx-target="#tabs-content"
        hx-push-url="true">
      <a>Data Access</a>
    </li>
  </ul>
</div>

<div id="tabs-content">
  {% include tab_partial %}
</div>
```

In the view, branch on the request: full page on a hard load, partial fragment on HTMX nav.
