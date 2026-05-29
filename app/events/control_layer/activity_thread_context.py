"""ActivityThreadContext — restricted alias of EventContext for non-event thread rows."""

from __future__ import annotations

from app.events.control_layer.event_context import EventContext
from app.events.control_layer.domain_structs.event_detail_struct import EventDetailStruct

# Inherits all thread operations (comments, attachments, file uploads, deletion)
# from EventContext with no overrides. Reserved for future asset-thread-specific
# divergence — if none materializes, it stays as-is.
class ActivityThreadContext(EventContext):
    pass


# ActivityThread rows and Event rows produce the same struct shape.
ActivityThreadStruct = EventDetailStruct
