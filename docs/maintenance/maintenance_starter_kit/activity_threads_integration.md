# Maintenance Activity Threads & Comments Integration Guide

Status: **Proposed Integration Pattern**

This document provides a comprehensive blueprint for integrating comments, file uploads, and activity feeds into the Maintenance application. It details how to leverage the existing `events` app infrastructure (`ActivityThread`, `ActivityThreadManager`, and reusable UI card fragments) for **Procedure Templates**, **Maintenance Plans**, and **Maintenance Events**.

---

## 1. Architectural Overview & Reusing Event App Endpoints

The EBAMS-2 event system provides a generic, reusable framework for comments and file attachments centered around:
- **`ActivityThread`**: A specific database row in the unified `event` table (via Multi-Table Inheritance/MTI) designated to hold comments and standalone attachments.
- **`ActivityThreadManager`**: The control layer utility managing thread visibility and providing the presentation context (`.card(user)`) for templates.
- **Reusable Fragments**: Located under `app/events/templates/events/fragments/` (`comments_card.html`, `files_card.html`, `event_card.html`). These accept standardized context dictionaries and handle HTMX-driven inline mutations (add/edit/delete/gallery modal).

### The "Zero Custom Code" Pattern
To avoid re-rolling comment and upload logic, we can route **100% of all activity interactions directly through the `events` app endpoints** (`comment_add`, `direct_attachment_add`, and `file_soft_delete`). 

For this to work out-of-the-box, the target thread must already exist (possessing a valid database primary key and `hash`). Therefore, we adopt the **Eager Thread Creation** pattern for versioned/scheduled entities.

---

## 2. Models & Schema Integration

To support activity feeds, the `TemplateActionSet` and `MaintenancePlan` models are associated with an `ActivityThread`. 

### 2.1 Schema Upgrades

#### Procedure Templates (`TemplateActionSet`)
Add a nullable, protected one-to-one relationship to `events.ActivityThread` in [template_action_set.py](file:///home/cb/REPOS/ebams2/app/maintenance/models/templates/template_action_set.py):
```python
activity_thread = models.OneToOneField(
    "events.ActivityThread",
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    related_name="procedure_template",
    help_text="Activity and document thread for this template version.",
)
```

#### Maintenance Plans (`MaintenancePlan`)
Add the corresponding field in [maintenance_plan.py](file:///home/cb/REPOS/ebams2/app/maintenance/models/planning/maintenance_plan.py):
```python
activity_thread = models.OneToOneField(
    "events.ActivityThread",
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    related_name="maintenance_plan",
    help_text="Activity and document thread for this maintenance plan.",
)
```

> [!IMPORTANT]
> **Migration Strategy:** Because these fields add new foreign keys to core models, developer environment databases should be rebuilt from scratch. Stop the dev server and run:
> ```bash
> python refresh_project.py
> ```

### 2.2 Eager Thread Creation (Publish & Create workflows)

Rather than lazy-creating threads on first write, we instantiate the `ActivityThread` during the entity's save/creation flow. This ensures that the thread hash is immediately available on first render.

#### In the Template Publish Step (e.g., `TemplateBuilderSessionAdapter.commit()`):
When committing a template builder draft to a published `TemplateActionSet`, create the thread:
```python
from app.events.models import ActivityThread

with transaction.atomic():
    thread = ActivityThread.objects.create(
        domain_id=draft.domain_id,
        created_by=actor,
        updated_by=actor,
    )
    template = TemplateActionSet.objects.create(
        ...,
        activity_thread=thread,
    )
```

#### In the Maintenance Plan Creation Step:
Create the thread when saving the new plan:
```python
with transaction.atomic():
    thread = ActivityThread.objects.create(
        domain_id=plan_data["domain_id"],
        created_by=actor,
        updated_by=actor,
    )
    plan = MaintenancePlan.objects.create(
        ...,
        activity_thread=thread,
    )
```

### 2.3 Thread Lifecycles Across Template Revisions

Procedure Templates are immutable once published. When a new revision of a template is drafted and published:
- **Revision Pattern:** Each template revision retains its own isolated `activity_thread`. Comments or files about "Revision 1" remain anchored to Revision 1.
- During `start_revision()`, the new `TemplateActionSet` starts with `activity_thread = None` (a blank slate), and a new thread is eagerly instantiated when the revision is published. This keeps version discussions clean.

---

## 3. Control Layer & Managers

Because thread creation is eagerly handled, the control layer's only responsibility is loading and framing the thread context for presentation.

### 3.1 Initializing the Context
In the respective context classes (e.g., `TemplateContext` and `MaintenancePlanContext`), retrieve the thread's presentation card:

```python
from app.events.presentation_layer.tools.generic_cards import build_activity_card

class TemplateContext:
    def __init__(self, template_id: int, actor):
        self.template = get_object_or_404(TemplateActionSet, pk=template_id)
        self.actor = actor

    def get_activity_card(self) -> dict:
        """Build the generic card dict contract for the template's thread."""
        if not self.template.activity_thread_id:
            # Fallback placeholder if thread was not eagerly created
            return {"hash": None, "comments": [], "event": {"allow_comments": True}, "direct_attachments": []}
        return build_activity_card(self.template.activity_thread, self.actor)
```

---

## 4. Presentation & Route Configuration

Because we reuse the events app's shared endpoints, **we write zero custom views, zero custom URLs, and zero redirect logic in the maintenance app.**

### 4.1 Reusing the Shared URLs
The events app provides the following URL routes, which accept any valid `ActivityThread` hash:
- **Add Comments:** `path("<str:event_hash>/comments/add/", comment_add, name="comment_add")`
- **Add Attachments:** `path("<str:event_hash>/attachments/add/", direct_attachment_add, name="direct_attachment_add")`
- **Delete File:** `path("files/<uuid:file_id>/delete/", file_soft_delete, name="file_soft_delete")` (automatically redirects to the referrer).

---

## 5. UI Integration & Template Markups

### 5.1 Procedure Templates (`template_detail.html`) & Plans (`planning_detail.html`)

To render the comments box and documents browser:
1. Ensure the web components scripts are loaded in the page block:
   ```django
   {% block content %}
   <script src="{% static 'web_components/file_browser.js' %}" defer></script>
   <script src="{% static 'web_components/app_specific/add_comment.js' %}" defer></script>
   <script src="{% static 'web_components/app_specific/comment_filter.js' %}" defer></script>
   ```
2. Render the components within the `body-grid`. 
   Wrap them in an outer container with `id="event-card-{{ comments_card.hash }}"` to allow HTMX outerHTML swaps to target and update the entire card area on the fly:
   
   ```django
   <div id="event-card-{{ comments_card.hash }}">
     <div class="body-grid has-rail">
       <div>
         <!-- ... standard detail columns ... -->
         
         <!-- Reusable comments card (automatically posts to comment_add and targets this parent div via hx-post) -->
         {% include "events/fragments/comments_card.html" with card=comments_card next=request.get_full_path row_depth="depth-3" action_depth="depth-4" %}
       </div>
       
       <div class="body-rail">
         <!-- Reusable files browser card -->
         {% include "events/fragments/files_card.html" with documents=comments_card.direct_attachments title="Template Documents" upload_modal_id="modal-upload-doc" %}
       </div>
     </div>
   </div>
   ```

3. Include the standard file upload dialog. Note that its form action points directly to `direct_attachment_add` in the events app, and uploads the fields as `files` (plural):
   ```django
   <dialog id="modal-upload-doc" class="card modal-styled" style="padding:0; max-width: 580px;">
     <form method="post" 
           action="{% url 'direct_attachment_add' event_hash=comments_card.hash %}" 
           enctype="multipart/form-data">
       {% csrf_token %}
       <header class="card-header">
         <p class="card-header-title">Upload Document</p>
         <button type="button" class="delete is-large" aria-label="close" commandfor="modal-upload-doc" command="close"></button>
       </header>
       <div class="card-content">
         <div class="field">
           <label class="label is-small">File</label>
           <div class="file is-small is-fullwidth has-name">
             <label class="file-label">
               <input class="file-input" type="file" name="files" required multiple
                      onchange="this.closest('.file').querySelector('.file-name').textContent = this.files.length ? this.files[0].name : 'No files selected';">
               <span class="file-cta"><span class="file-icon"><span class="material-icons">upload</span></span><span class="file-label">Choose files…</span></span>
               <span class="file-name">No files selected</span>
             </label>
           </div>
         </div>
         <div class="field">
           <label class="label is-small">Caption (optional)</label>
           <input class="input is-small" type="text" name="caption">
         </div>
       </div>
       <footer class="card-footer custom-card-footer">
         <div class="card-footer-secondaries">
           <button type="button" class="button is-light" commandfor="modal-upload-doc" command="close">Cancel</button>
         </div>
         <button type="submit" class="button is-medium is-link card-footer-primary">Upload</button>
       </footer>
     </form>
   </dialog>
   ```

---

## 6. Maintenance Events Integration (`detail.html` & `work.html`)

Since `MaintenanceDetail` directly inherits from `Event` (MTI), it is already a valid database target for the comments and attachments engine. 

### 6.1 Building the Event Card Context
In both [event_views.py](file:///home/cb/REPOS/ebams2/app/maintenance/presentation_layer/entrypoints/event_views.py) and [work_views.py](file:///home/cb/REPOS/ebams2/app/maintenance/presentation_layer/entrypoints/work_views.py), import `build_activity_card` and add the card to the template context:

```python
from app.events.presentation_layer.tools.generic_cards import build_activity_card

def maintenance_detail(request: HttpRequest, pk: int) -> HttpResponse:
    # ... loading detail record ...
    context = {
        "detail": detail,
        # ... other context variables ...
        "activity_card": build_activity_card(detail, request.user),
    }
    return render(request, "maintenance/detail.html", context)
```

### 6.2 Render and HTMX Swap Setup
By including `events/fragments/event_card.html` at the bottom of the page, all interactive actions (leaving comments, attaching files inline) work seamlessly. HTMX will automatically swap the updated card content in place without reloading the entire parent page.

#### In `maintenance/detail.html` and `maintenance/work.html`
Append the following at the bottom of the primary block:

```django
<div class="mt-5">
  <h2 class="title is-5 mb-3">Event Activity & Documentation</h2>
  {% include "events/fragments/event_card.html" with card=activity_card %}
</div>
```
