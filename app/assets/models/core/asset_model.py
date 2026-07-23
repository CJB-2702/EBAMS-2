from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetModel(AuditFieldsMixin):
    """
    Product definition for a type of asset. Replaces the old MakeModel.
    Supports a self-referential revision tree: revisions reference a base model.

    Identity is (model_name, version) — unique. Example, left-to-right:
    Toyota / Corolla / 2016  →  manufacturer / model_name / version.

    ``config_baselines`` is NOT part of identity: it is the allow-list of acceptable
    trim/spec baselines an individual Asset may declare (e.g. ["LE", "EX", "SE"]).
    One model row therefore spans every baseline instead of proliferating a row per
    trim. The per-asset value lives on ``Asset.config_baseline`` and is soft-validated
    against this list at the UI layer only (no hard DB/server enforcement).
    """

    model_name = models.CharField(max_length=200)
    version = models.CharField(max_length=100, blank=True, default="")
    # Manual integer rank ordering versions of a model line low→high (older/base =
    # lower). The ``version`` string ("2016", "M5", "C") does not sort meaningfully,
    # so this drives display order. Unassigned = NULL. Not part of identity.
    version_rank = models.PositiveIntegerField(null=True, blank=True)
    config_baselines = models.JSONField(default=list, blank=True)

    is_base_model = models.BooleanField(default=True)
    base_model = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="revisions",
        null=True,
        blank=True,
    )

    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.PROTECT,
        related_name="models",
    )

    meter1_unit = models.CharField(max_length=100, null=True, blank=True)
    meter2_unit = models.CharField(max_length=100, null=True, blank=True)
    meter3_unit = models.CharField(max_length=100, null=True, blank=True)
    meter4_unit = models.CharField(max_length=100, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    # Two model-level activity surfaces, each lazily created on first write and
    # decoupled from any single version. Like a Part definition, an AssetModel is a
    # shared record spanning domains, so neither thread's own ``domain`` is
    # authoritative for access (see the ActivityThread docstring) — the value written
    # is an incidental bootstrap.
    #   documentation — the technical document library plus the human comments shown
    #     on the model's library page (an ActivityThread: comments + attachments).
    #   photo_gallery — the model's image gallery (a FileSet: attachments only).
    documentation = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        related_name="asset_model_documentation",
        null=True,
        blank=True,
    )
    photo_gallery = models.OneToOneField(
        "events.FileSet",
        on_delete=models.PROTECT,
        related_name="asset_model_photo_gallery",
        null=True,
        blank=True,
    )

    # Hero image — points at one image Attachment on this model's photo_gallery.
    # SET_NULL is a safety net; the image manager keeps this in sync.
    primary_image = models.ForeignKey(
        "events.Attachment",
        on_delete=models.SET_NULL,
        related_name="primary_of_asset_model",
        null=True,
        blank=True,
    )

    # No provisioning state lives here — it is tracked in a separate state table
    # owned by the extensions app (P2 / E7). assets owns no such state.

    manufacturers = models.ManyToManyField(
        "assets.Manufacturer",
        through="assets.ModelManufacturer",
        related_name="models",
    )
    domains = models.ManyToManyField(
        "administration.Domain",
        through="assets.ModelDomain",
        related_name="asset_models",
    )

    class Meta:
        db_table = "asset_model"
        ordering = ["model_name", "version_rank", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["model_name", "version"],
                name="uq_assetmodel_identity",
            ),
        ]

    def __str__(self) -> str:
        parts = [self.model_name]
        if self.version:
            parts.append(self.version)
        return " — ".join(parts)
