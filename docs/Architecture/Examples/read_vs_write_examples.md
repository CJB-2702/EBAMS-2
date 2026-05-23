# Read vs write examples

Concrete illustrations of the rules in [../layer_rules.md](../layer_rules.md). Each example shows allowed and not-allowed code shapes side by side.

## Allowed: thin read in the endpoint

**Use case:** Read-only list of events with comment counts for a dashboard fragment.

**OK:** Entrypoint calls `Event.objects.filter(...).annotate(comment_count=Count("comments"))` or delegates one small `search.events_for_dashboard()` that only touches the event + comment relationship. Still **no writes** in the entrypoint.

## Allowed: simple event + comments detail

**Use case:** Event detail page showing the event row and its comments.

**OK:** `Event.objects.prefetch_related("comments").get(pk=...)` in the entrypoint or a one-function search helper. Two main concerns (event + comments). **Creates** for new comments still go through control layer (e.g. POST handler calls `control_layer.comments.add_comment(...)`).

## Not allowed: fat query in the endpoint

**Use case:** Maintenance event screen with comments, attachments, actions, headers, parts, assignees, etc.

**Avoid:** Fifty lines of ORM in `entrypoints/maintenance_event_detail.py`.

**Do instead:** `MaintenanceEventDetail = load_maintenance_event_detail(event_id)` implemented in `presentation_layer/search/maintenance_events.py` (or a loader paired with `domain_structs/maintenance_event_detail.py`) with all `prefetch_related` / `select_related` spelled out once.

## Writes always via control layer

**Use case:** User submits a form to add a comment.

**Endpoint:** Parses POST, then calls e.g. `control_layer.comments.add_comment(event_id=..., body=..., user=...)`.

**Not allowed:** `Comment.objects.create(...)` inside the entrypoint.

---

## Sketch: maintenance event detail with a domain struct

```python
# presentation_layer/search/maintenance_events.py
def load_maintenance_event_detail(event_id):
    event = (
        MaintenanceEvent.objects
        .select_related("domain", "created_by")
        .prefetch_related(
            "comments__attachments__file",
            "actions__parts",
            "headers",
        )
        .get(pk=event_id)
    )
    return MaintenanceEventDetail(event=event)

# entrypoints/maintenance_event_detail.py
def maintenance_event_detail(request, event_id):
    detail = load_maintenance_event_detail(event_id)
    return render(request, "maintenance_event/detail.html", {"detail": detail.as_dict()})
```

The entrypoint stays a thin traffic controller; all the prefetch strategy lives in `search/`, and the struct gives the template a stable shape.
