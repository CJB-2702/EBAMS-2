---
type: "Technical Decision"
title: "ActivityThread implemented as a limited proxy of Event"
description: "ActivityThread is a **Django proxy model** that inherits from Event — not a separate model, and not a parent model that Event extends."
tags: [technical-decisions, technical-decision, history]
context_tier: 2
---

# ActivityThread implemented as a limited proxy of Event

- **Date:** 2026-05-28
- **Context / feature:** Activity threads (photo galleries, documentation threads, etc.) that hang off assets and share Comment/Attachment infrastructure with Events.

## Decision

`ActivityThread` is a **Django proxy model** that inherits from `Event` — not a separate model, and not a parent model that Event extends.

```python
class ActivityThread(Event):
    objects = AssetThreadManager()  # excludes event rows
    class Meta:
        proxy = True
```

No new DB table or columns are created. Thread rows live in the `event` table, distinguished by `thread_type != "event"`. Event-specific required fields (`title`, `event_type`) are satisfied at save time by writing a sentinel value (`"__thread__"`) so the NOT NULL constraints are never violated.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Event extends ActivityThread (ActivityThread as parent) | Performance: every `Event.objects.all()` query would need a join or filter to exclude thread rows; Event is the high-volume model |
| Separate `ActivityThread` table with shared abstract base | Schema complexity; Comment and Attachment FKs would need to target two tables or a GenericFK |
| Single model with `thread_type` filter on every query | No semantic separation — any queryset that forgot the filter would silently return mixed data |

## Rationale

- **Zero migration cost.** The proxy shares the `event` table; schema is unchanged.
- **Filtered queryset by default.** `AssetThreadManager.get_queryset()` excludes event rows, so `ActivityThread.objects` is always scoped correctly.
- **Semantic FK target.** `Comment.activity_thread` and `Attachment.thread` point to `ActivityThread`, making the intent explicit in the model graph without a polymorphic or generic relation.
- **Event queries stay fast.** `Event.objects.all()` is unaffected — no join, no extra filter.

## Sentinel pattern

Non-event rows satisfy Event's NOT NULL string fields by storing `"__thread__"` in `title` and `event_type` on `save()`. The value is intentionally ugly so it is never confused for real data and is easy to grep for in raw SQL.

## Related

- `app/events/models/activity_thread_proxy.py` — implementation
- `app/events/models/event.py` — `ActivityThreadType` enum and `thread_type` field
- `Activity_Thread_Migration_Project/phase_3/activity_and_event_limited_proxy_alias.md` — the design document that informed this decision
