"""The printed barcode token vocabulary (intake_portal_workflow.md §9.4).

| Object         | Encoded value |
| :------------- | :------------ |
| Intake session | `INTAKE-8`    |
| Shipment       | `SHIP-142`    |

WHY A PREFIX AND NOT A BARE INTEGER. The prefix costs nothing and prevents an
entire class of mistake: a bare `8` scanned into the item field is
indistinguishable from a quantity or a short SKU and will be silently
mis-recorded. `INTAKE-8` is self-identifying — the scan handler knows
immediately that it was pointed at the wrong field and can say so, which is
the difference between a confusing count and a corrected one.

BARCODES RENDER ON THE PRINTOUT ONLY (Q14). No barcode appears anywhere in the
web UI. Scanning a computer screen does work and people will discover that,
but it is not the intended way of working and the system should not invite it.
Paper is the scannable surface; the screen is the working surface.

The closed loop worth noticing (§9.6): the shipment barcodes on the printout
are what the operator scans to set the active shipment on the record page.
Print the sheet, carry it to the dock, scan the shipment header off the paper,
then scan the items under it.
"""

from __future__ import annotations

import re

SESSION_PREFIX = "INTAKE"
SHIPMENT_PREFIX = "SHIP"

_TOKEN_RE = re.compile(r"^(INTAKE|SHIP)-(\d+)$")


def session_token(session_id: int) -> str:
    return f"{SESSION_PREFIX}-{session_id}"


def shipment_token(shipment_id: int) -> str:
    return f"{SHIPMENT_PREFIX}-{shipment_id}"


def parse_token(payload: str) -> tuple[str, int] | None:
    """Return `(kind, id)` for a recognised token, or None for anything else.

    Exact and case-sensitive, like the `CMDX` namespace: a real SKU that
    happens to contain "SHIP" is a SKU.
    """
    match = _TOKEN_RE.match((payload or "").strip())
    if match is None:
        return None
    return match.group(1), int(match.group(2))
