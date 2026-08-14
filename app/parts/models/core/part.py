from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class Part(AuditFieldsMixin):
    """The engineering hub. Part.id is the only thing the wider app references (D3)."""

    part_number = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    part_type = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    # Domain scoping (D14) — default False = visible to all authenticated users.
    is_domain_limited = models.BooleanField(default=False)

    # Two Part-level threads, each lazily created on first write (D5), both
    # decoupled from revisions:
    #   documents_thread — the technical library (design docs, work instructions,
    #     specifications) plus the Part audit feed (machine comments) and human
    #     comments shown on the detail page.
    #   gallery_thread — the Part's photo gallery. Its comments are a backend-only
    #     audit history (gallery image added/removed/set-primary) and are never
    #     displayed to end users — for administrators and data engineers only.
    documents_thread = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        related_name="part_documents_thread",
        null=True,
        blank=True,
    )
    gallery_thread = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        related_name="part_gallery_thread",
        null=True,
        blank=True,
    )

    # Hero image — points at one image Attachment on the part's gallery_thread. No
    # separate FileSet: an ActivityThread already carries attachments. SET_NULL is
    # a safety net; the image manager keeps this in sync.
    primary_image = models.ForeignKey(
        "events.Attachment",
        on_delete=models.SET_NULL,
        related_name="primary_of_part",
        null=True,
        blank=True,
    )

    # Denormalized pointers for the common case: a part with exactly one active
    # supplier item. Avoids a join for the majority-case manufacturer/supplier
    # lookup. SupplierItem remains the source of truth; SupplierItemManager keeps
    # these in sync. SET_NULL because these are denormalization, not ownership.
    primary_manufacturer = models.ForeignKey(
        "parts.PartManufacturer",
        on_delete=models.SET_NULL,
        related_name="simple_parts",
        null=True,
        blank=True,
    )
    primary_supplier_item = models.ForeignKey(
        "parts.SupplierItem",
        on_delete=models.SET_NULL,
        related_name="simple_part_of",
        null=True,
        blank=True,
    )
    is_simple_part = models.BooleanField(default=False)

    class Meta:
        db_table = "part"
        ordering = ["part_number"]

    def __str__(self) -> str:
        return f"{self.part_number} — {self.name}"
