"""Template context available on every page.

The two session-backed work queues (issuance and purchasing) need a badge in
the shared topnav, which every sub-app's `base.html` includes. A context
processor is the only seam that reaches all of them without every entrypoint
in the project having to remember to pass the counts.

Both counts are a session dict lookup and a `len()` — no database query. The
queue *contents* are fetched lazily by the popover's own htmx fragment, so
opening a page costs nothing extra and only opening the dropdown costs a read.
"""

from __future__ import annotations

from app.inventory.presentation_layer.tools import issuance_draft
from app.procurement.presentation_layer.tools import purchasing_queue


def work_queues(request) -> dict:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"issuance_queue_count": 0, "purchasing_queue_count": 0}
    return {
        "issuance_queue_count": issuance_draft.count(request),
        "purchasing_queue_count": purchasing_queue.count(request),
    }
