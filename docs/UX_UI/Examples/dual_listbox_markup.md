# Dual listbox markup

Canonical fragments for the component described in [../dual_listbox.md](../dual_listbox.md).

## Fragment template (`_<relationship>_dlb_only.html`)

The fragment is the **root** element of the response — no outer wrapper. HTMX swaps it via `outerHTML`.

```html
<dual-list-box id="user-roles-dlb">
  <list-box id="user-roles-avail" slot="left" label="Available">
    <input slot="search" type="text" class="input is-small" placeholder="Filter..." />
    <select multiple>
      {% for role in available_roles %}
        <option value="{{ role.pk }}" data-label="{{ role.name }}">{{ role.name }}</option>
      {% endfor %}
    </select>
  </list-box>

  <div slot="controls" class="dlb-controls">
    <button hx-post="{% url 'user_move_roles' target_user.pk %}"
            hx-vals="js:{item_ids: listBox('user-roles-avail').selected(), direction: 'add'}"
            hx-target="#user-roles-dlb"
            hx-swap="outerHTML swap:1s"
            class="button is-small">→</button>
    <button hx-post="{% url 'user_move_roles' target_user.pk %}"
            hx-vals="js:{item_ids: listBox('user-roles-assigned').selected(), direction: 'remove'}"
            hx-target="#user-roles-dlb"
            hx-swap="outerHTML swap:1s"
            class="button is-small">←</button>
  </div>

  <list-box id="user-roles-assigned" slot="right" label="Assigned">
    <input slot="search" type="text" class="input is-small" placeholder="Filter..." />
    <select multiple>
      {% for role in assigned_roles %}
        <option value="{{ role.pk }}" data-label="{{ role.name }}">{{ role.name }}</option>
      {% endfor %}
    </select>
  </list-box>
</dual-list-box>
```

## Endpoint response shape

Every move endpoint returns:

```html
<toast-alert type="success" dismiss-delay="3000">
  Items added to the list.
</toast-alert>
<dual-list-box id="user-roles-dlb">
  <!-- refreshed list-boxes with updated available/assigned items -->
</dual-list-box>
```

Error responses use `type="danger"` and `dismiss-delay="0"` (manual dismiss only).

## Page load — component scripts

Load the three web components once per page that uses the pattern:

```html
{% block extra_head %}
  <script src="{% static 'web_components/list_box.js' %}"></script>
  <script src="{% static 'web_components/dual_listbox.js' %}"></script>
  <script src="{% static 'web_components/toast_alert.js' %}"></script>
  <style>
    toast-alert {
      --toast-max-width: 1216px;
    }
  </style>
{% endblock %}
```

## Side-effect pattern (e.g. inherited-permissions refresh)

```javascript
document.addEventListener('list-box-change', function (e) {
  const lb = e.target;
  if (lb.id !== 'up-perms-avail') return;

  const url = lb.dataset.permCheckUrl;
  htmx.ajax('POST', url, {
    target: '#up-perms-inherit-panel',
    swap: 'innerHTML',
    values: { csrfmiddlewaretoken: CSRF, permission_ids: e.detail.values },
  });
});
```
