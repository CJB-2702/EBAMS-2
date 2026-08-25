"""The only generator of `PartIssueSession.session_number`.

Extracted from `PartIssuanceOrchestrator.commit_session`, which built the
string inline with a local `import uuid` and no collision handling despite the
column being `unique=True`. A receipt number is a piece of the domain's
vocabulary — storeroom staff read it aloud, write it on paperwork, and search
for it — so its format belongs somewhere nameable rather than buried in a
transaction body.
"""

from __future__ import annotations

import uuid

from django.utils import timezone

from app.inventory.models import PartIssueSession

#: How many times to retry on the (vanishingly unlikely) suffix collision
#: before giving up. A retry is cheap; a lost receipt is not.
_MAX_ATTEMPTS = 5

PREFIX = "ISS"


class IssueSessionNumberFactory:
    @classmethod
    def next_number(cls, *, issued_at=None) -> str:
        """`ISS-20260824-A1B2C3` — prefix, handover date, random suffix.

        Dated by the handover, not by `timezone.now()`, so a receipt
        back-dated to when the parts actually changed hands reads correctly.
        Deliberately random rather than a per-day sequence: a sequence needs a
        counter row and a lock, and nothing here depends on receipts being
        consecutive.
        """
        stamp = (issued_at or timezone.now()).strftime("%Y%m%d")
        for _ in range(_MAX_ATTEMPTS):
            candidate = f"{PREFIX}-{stamp}-{uuid.uuid4().hex[:6].upper()}"
            if not PartIssueSession.objects.filter(session_number=candidate).exists():
                return candidate
        raise RuntimeError(
            f"Could not generate a unique issue session number after "
            f"{_MAX_ATTEMPTS} attempts."
        )
