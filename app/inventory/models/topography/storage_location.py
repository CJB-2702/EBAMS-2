from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class StorageLocation(AuditFieldsMixin):
    """One addressable XYZ coordinate within a room, anchored on its parent
    `RoomLocation` (XY) plus its own `atomic_coord` (Z). `display_code` is
    computed on write by the control layer (`coordinate_adaptor`), never here
    — models hold no business logic (FD-16). Major/minor coordinates live
    exclusively on `RoomLocation` (FD-29) — this is the single source of
    truth, not a denormalized copy."""

    room_location = models.ForeignKey(
        "inventory.RoomLocation",
        on_delete=models.CASCADE,
        related_name="storage_locations",
    )
    atomic_coord = models.CharField(max_length=50)
    display_code = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "inventory_storage_location"
        ordering = ["room_location", "atomic_coord"]
        constraints = [
            models.UniqueConstraint(
                fields=["room_location", "atomic_coord"],
                name="uniq_storage_location_coord",
            ),
        ]
        indexes = [
            models.Index(
                fields=["room_location", "display_code"], name="storage_loc_room_code_idx"
            ),
        ]

    @property
    def room(self):
        return self.room_location.room

    @property
    def room_id(self):
        return self.room_location.room_id

    def __str__(self) -> str:
        return f"{self.room_location} @ {self.display_code}"
