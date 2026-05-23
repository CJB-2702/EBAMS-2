# Card footer markup

Canonical card-footer HTML for the geometry described in [../form_style_guide.md](../form_style_guide.md).

## Edit form — Cancel / Reset / Delete + Save

```html
<footer class="card-footer custom-card-footer">
  <div class="card-footer-secondaries">
    <a href="…" class="button is-small is-light">Cancel</a>
    <button type="reset" class="button is-small is-light">Reset</button>
    <button type="submit"
            class="button is-small is-danger is-light"
            formaction="{% url 'role_delete' role.id %}"
            onclick="return confirm('Delete this role?');">
      Delete
    </button>
  </div>
  <button type="submit" class="button is-primary card-footer-primary">Save</button>
</footer>
```

## Primary-only footer (no secondaries)

Keep the empty secondaries container for the left column so the grid stays balanced.

```html
<footer class="card-footer custom-card-footer">
  <div class="card-footer-secondaries"></div>
  <button type="submit" class="button is-primary card-footer-primary">Save</button>
</footer>
```

## Read-only card with Delete (secondary) and Edit (primary)

```html
<footer class="card-footer custom-card-footer">
  <div class="card-footer-secondaries">
    <form method="post" action="{% url 'event_soft_delete' hash=event_hash %}" style="margin: 0;">
      {% csrf_token %}
      <button class="button is-small is-danger is-light" type="submit"
        onclick="return confirm('Delete this event?');">
        <span class="icon"><span class="material-icons" aria-hidden="true">delete</span></span>
        <span>Delete</span>
      </button>
    </form>
  </div>
  <a href="{% url 'event_edit' hash=event_hash %}" class="button is-small is-info is-light card-footer-primary">
    <span class="icon"><span class="material-icons" aria-hidden="true">edit</span></span>
    <span>Edit</span>
  </a>
</footer>
```

## Inline single-field form

```html
<form method="post" action="{% url 'domain_rename' domain.id %}"
      hx-post="{% url 'domain_rename' domain.id %}"
      hx-target="#domain-name-block"
      hx-swap="outerHTML">
  {% csrf_token %}
  <div class="field has-addons">
    <div class="control is-expanded">
      <input class="input is-family-monospace"
             type="text" name="name"
             value="{{ domain.name }}"
             required>
    </div>
    <div class="control">
      <button type="submit" class="button is-primary">Save</button>
    </div>
  </div>
</form>
```
