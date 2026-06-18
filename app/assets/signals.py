"""Asset lifecycle signals — the assets app's only outward announcement surface.

Defining and sending a ``Signal`` creates **no** dependency on any listener: assets
announces "this happened" and stays ignorant of who reacts. ``detail_extensions``
(and any future listener) imports these to connect — the allowed direction.

Both are sent as the **final in-transaction statement** of creation, after the owner
and its sibling create-steps (meter / tree / eventing / capability) are settled, so a
receiver sees a fully-built owner. Receivers schedule their work with
``transaction.on_commit`` — nothing runs for a rolled-back create.

Do **not** use Django's ``post_save``: it fires before the orchestrator's later steps,
so the owner would not yet be complete.
"""

from __future__ import annotations

from django.dispatch import Signal

# kwargs: asset (Asset), actor_id (int | None)
asset_created = Signal()

# kwargs: model (AssetModel), actor_id (int | None)
asset_model_created = Signal()
