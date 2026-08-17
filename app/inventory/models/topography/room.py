from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class Room(AuditFieldsMixin, SoftDeleteMixin):
    """A room within a warehouse. Exactly one room per warehouse is the
    protected Intake Room (`is_intake_room`), created by `WarehouseFactory`
    and guarded against rename/delete by `RoomPolicy` (FD-14).

    `photo_gallery` + `current_layout` carry the room's Tier-1 spatial map
    (FD-29): a lazily-created `events.FileSet` gallery of uploaded SVG
    layouts, with `current_layout` pointing at the live one — same shape as
    `Asset.photo_gallery`/`primary_image`, named for layout semantics.
    """

    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    room_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    photo_gallery = models.OneToOneField(
        "events.FileSet",
        on_delete=models.PROTECT,
        related_name="photo_gallery_room",
        null=True,
        blank=True,
    )
    current_layout = models.ForeignKey(
        "events.Attachment",
        on_delete=models.SET_NULL,
        related_name="current_layout_of_room",
        null=True,
        blank=True,
    )
    is_intake_room = models.BooleanField(default=False)
    is_deletable = models.BooleanField(default=True)
    is_renamable = models.BooleanField(default=True)
    excluded_domains = models.ManyToManyField(
        "administration.Domain",
        related_name="excluded_rooms",
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "inventory_room"
        ordering = ["warehouse", "room_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "room_name"], name="uniq_room_warehouse_name"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.warehouse.code} / {self.room_name}"
