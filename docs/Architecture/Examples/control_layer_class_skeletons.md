# Control-layer class skeletons

Concrete shapes for the patterns described in [../oop_control_patterns.md](../oop_control_patterns.md). These are illustrative, not copy-paste boilerplate — they show the conventional signatures and docstring shapes.

## Struct

```python
# control_layer/domain_structs/maintenance_event_struct.py
class MaintenanceEventStruct:
    """Aggregate read model for a single maintenance event.

    Always loads the event row and validates it exists. Comments,
    attachments, actions, parts, and headers may be eager- or lazy-loaded.
    """

    def __init__(self, event_id, *, eager=True):
        self.event = MaintenanceEvent.objects.select_related("domain").get(pk=event_id)
        if eager:
            self._load_all()

    @property
    def comments(self):
        ...

    def to_dict(self):
        ...
```

## Context

```python
# control_layer/maintenance_event_context.py
class MaintenanceEventContext:
    """Entry point for control logic around one maintenance event id."""

    def __init__(self, event_id, actor, *, eager=True):
        self.actor = actor
        self.struct = MaintenanceEventStruct(event_id, eager=eager)

    @classmethod
    def from_struct(cls, struct, actor):
        instance = cls.__new__(cls)
        instance.actor = actor
        instance.struct = struct
        return instance

    @property
    def action_manager(self):
        ...

    def add_comment(self, data):
        return CommentHandler(self.actor).add(self.struct.event, data)
```

## Handler vs Manager

```python
# control_layer/handlers/maintenance_event_close_handler.py
class MaintenanceEventCloseHandler:
    """Single-task specialist: closes one maintenance event end-to-end."""

    def __init__(self, actor):
        self.actor = actor

    def close(self, event_id, payload):
        ...


# control_layer/managers/maintenance_action_manager.py
class MaintenanceActionManager:
    """Manager for the 'actions' sub-area of a maintenance event."""

    def __init__(self, context):
        self.context = context

    def update_costs(self):
        ...

    def get_completion_percentage(self):
        ...
```

## Guard (Policy / Validator / StateMachine)

```python
# control_layer/guards/maintenance_event_close_guard.py
"""Guard type: Policy. Guards transition-to-closed on MaintenanceEvent.

May this actor close this maintenance event given its current state and
the actor's role / domain membership?
"""

class MaintenanceEventClosePolicy:
    def __init__(self, actor, event):
        ...

    def assert_allowed(self):
        ...
```

## Factory and BulkFactory

```python
# control_layer/factories/maintenance_event_factory.py
class MaintenanceEventFactory:
    """Stateless creation of a root MaintenanceEvent from structured data."""

    @classmethod
    def create_event(cls, structured_data):
        ...
        return MaintenanceEventStruct(event.pk)


class BulkMaintenanceEventFactory:
    """Batch creation. Returns a list of MaintenanceEvent rows only."""

    @classmethod
    def create(cls, data_rows):
        ...
        return events
```
