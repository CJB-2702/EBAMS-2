# Search Row Cards Pattern

This design pattern is used for displaying search results and lists with enhanced information density. It replaces traditional grid tables with row-based cards where each card takes up the full width of the container. 

Key metadata and status indicators are placed inline within the card header, while actions are positioned as flush, full-height panels on the right side of the card.

---

## Pattern Anatomy

```
+-------------------------------------------------------------------------------+----------+
|  Title  [Category Tag]                             Stats | Status Tag |   Action |
+-------------------------------------------------------------------------------+   edit   |
|                                                                               |  (Info)  |
|  Card Body Content (e.g. Description / Detail Sub-tables)                     +----------+
|                                                                               |  Delete  |
|                                                                               | (Danger) |
+-------------------------------------------------------------------------------+----------+
```

1. **Outer Card**: Horizontal flex layout (`flex-direction: row; align-items: stretch`) to keep actions flush and full-height.
2. **Left Content Pane**: Vertically stacked header and body (`display: flex; flex-direction: column; flex-grow: 1;`).
3. **Card Header**: Displays Title, Tags, and Stats inline in a single row across the header.
4. **Right Action Pane**: Flush, thin, full-height column containing one or more action buttons.

---

## Canonical HTML Example

```html
<div class="card" style="display: flex; flex-direction: row; align-items: stretch; overflow: hidden; box-shadow: var(--bulma-card-shadow); border-radius: 0;">
  
  <!-- Left Content Pane -->
  <div style="flex-grow: 1; display: flex; flex-direction: column; min-width: 0; border-right: 1px solid var(--bulma-border-light);">
    
    <!-- Inline Card Header -->
    <header class="card-header" style="background-color: var(--bulma-scheme-main-bis); border-bottom: 1px solid var(--bulma-border-light); box-shadow: none; display: block; padding: 0.75rem 1rem; border-radius: 0;">
      <div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1rem; width: 100%;">
        <!-- Left Side: Title & Badge Tags -->
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <span class="title is-6 mb-0">{{ item.name }}</span>
          <span class="tag is-info is-light is-small">{{ item.category }}</span>
        </div>
        
        <!-- Right Side: Key Metadata / Stats / Status -->
        <div style="display: flex; align-items: center; gap: 1.25rem; font-size: 0.75rem;" class="has-text-grey-dark">
          <div>
            <span class="has-text-grey">Stats:</span>
            <span class="tag is-light is-small">{{ item.count }} models</span>
          </div>
          {% include "assets/_status_tag.html" with value=item.is_active|yesno:"Active,Inactive" %}
        </div>
      </div>
    </header>

    <!-- Card Content -->
    <div class="card-content" style="flex-grow: 1; padding: 1rem;">
      <div class="content is-size-7">
        <p class="has-text-grey-dark mb-3">{{ item.description }}</p>
        
        <!-- Nested Table or Details -->
        <div style="border-top: 1px solid var(--bulma-border-light); padding-top: 0.75rem;">
          <!-- Detail lists or sub-tables go here -->
        </div>
      </div>
    </div>
  </div>

  <!-- Right Action Pane (Side-by-side Flush Buttons) -->
  <div style="display: flex; flex-direction: row; align-items: stretch; flex-shrink: 0;">
    <!-- Edit Action (Primary Navigation) -->
    <a href="{% url 'item_edit' item.id %}" 
       class="button is-info is-light" 
       style="display: flex; flex-direction: column; justify-content: center; align-items: center; width: 80px; height: auto; flex-shrink: 0; border: none; border-radius: 0; gap: 0.25rem;">
      <span class="icon" style="margin: 0;"><span class="material-icons" style="font-size: 1.5rem;">edit</span></span>
      <span style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">edit</span>
    </a>

    <!-- Delete Action (Secondary Destructive) -->
    <form method="post" action="{% url 'item_delete' item.id %}" style="display: flex; margin: 0;">
      {% csrf_token %}
      <button type="submit" 
              class="button is-danger is-light" 
              style="display: flex; flex-direction: column; justify-content: center; align-items: center; width: 80px; height: auto; flex-shrink: 0; border: none; border-radius: 0; gap: 0.25rem;"
              onclick="return confirm('Are you sure you want to delete this?');">
        <span class="icon" style="margin: 0;"><span class="material-icons" style="font-size: 1.5rem;">delete</span></span>
        <span style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">delete</span>
      </button>
    </form>
  </div>

</div>
```

---

## Styling Guidelines

- **Sharp Corners**: Use `border-radius: 0;` on the outer card, the header, and all action buttons/forms.
- **Heights**: The right action buttons must have `height: auto;` to fill the vertical height of the card, while the parent container has `align-items: stretch;`.
- **Widths**: Action buttons must be relatively thin, typically `80px`.
- **Text & Icon Layout**: Icons are stacked vertically above uppercase labels with minor letter spacing (`letter-spacing: 0.05em`).
- **Separators**: A subtle border (`border-right: 1px solid var(--bulma-border-light)`) divides the left content pane from the right action pane. No borders exist between side-by-side action buttons to keep them flush.
