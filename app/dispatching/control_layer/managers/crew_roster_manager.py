"""Manager: crew roster on the dispatch — personnel belong here, never on a
reservation (dispatching_starter_kit/3_asset_reservations.md §11)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.narrators.dispatch_narrator import DispatchNarrator
from app.dispatching.models.enums import PersonnelRole
from app.dispatching.models.line_items.dispatch_personnel import DispatchPersonnel

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class CrewRosterManager:
    def __init__(self, dispatch_context) -> None:
        self._ctx = dispatch_context

    @property
    def dispatch(self):
        return self._ctx.dispatch

    def add(
        self, *, user_id: int, role: str = PersonnelRole.PASSENGER, notes: str = "", actor: "AbstractUser",
    ) -> DispatchPersonnel:
        if DispatchPersonnel.objects.filter(dispatch=self.dispatch, user_id=user_id).exists():
            raise ValueError("This person is already on the crew for this dispatch.")

        with transaction.atomic():
            crew_member = DispatchPersonnel.objects.create(
                dispatch=self.dispatch,
                user_id=user_id,
                role=role,
                notes=notes,
                created_by=actor,
                updated_by=actor,
            )

        self._ctx._narrate(
            DispatchNarrator.crew_added(
                username=getattr(crew_member.user, "username", str(user_id)), role=role
            )
        )
        self._ctx.refresh()
        return crew_member

    def remove(self, *, crew_id: int, actor: "AbstractUser") -> None:
        crew_member = DispatchPersonnel.objects.select_related("user").get(
            pk=crew_id, dispatch_id=self.dispatch.pk
        )
        username = getattr(crew_member.user, "username", str(crew_member.user_id))
        with transaction.atomic():
            crew_member.delete()

        self._ctx._narrate(DispatchNarrator.crew_removed(username=username))
        self._ctx.refresh()
