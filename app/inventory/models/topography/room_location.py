from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class RoomLocation(AuditFieldsMixin):
    """One addressable XY coordinate within a room (Tier 2 of the SVG spatial
    engine, FD-29). `display_code` is XY-only (e.g. `"0005-0002"`), computed
    on write by the control layer (`coordinate_adaptor`), never here.

    `photo_gallery` + `current_layout` carry this RoomLocation's own Tier-3
    Z-picker SVG — same gallery pair shape as `Room.photo_gallery`. A
    RoomLocation with no `current_layout` and exactly one child
    `StorageLocation` is the "skip tier 3" case: the UI drills straight to
    the stock drawer instead of a pointless third click.
    """

    room = models.ForeignKey(
        "inventory.Room",
        on_delete=models.CASCADE,
        related_name="room_locations",
    )
    major_coord = models.CharField(max_length=50)
    minor_coord = models.CharField(max_length=50)
    display_code = models.CharField(max_length=100)
    photo_gallery = models.OneToOneField(
        "events.FileSet",
        on_delete=models.PROTECT,
        related_name="photo_gallery_room_location",
        null=True,
        blank=True,
    )
    current_layout = models.ForeignKey(
        "events.Attachment",
        on_delete=models.SET_NULL,
        related_name="current_layout_of_room_location",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "inventory_room_location"
        ordering = ["room", "major_coord", "minor_coord"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "major_coord", "minor_coord"],
                name="uniq_room_location_coord",
            ),
        ]
        indexes = [
            models.Index(fields=["room", "display_code"], name="room_loc_room_code_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.room} @ {self.display_code}"
