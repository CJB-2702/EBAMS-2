from django.db import models


class AbstractRequirement(models.Model):
    """Shared informational fields for a dispatch or template requirement row.

    Required vs preferred is informational only — neither filters nor blocks
    anything automatically. See dispatching_starter_kit/2_dispatch.md §6.1.
    """

    is_required = models.BooleanField(
        default=True,
        help_text="True = required, False = preferred. Informational only.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        abstract = True


class AbstractCapabilityRequirement(AbstractRequirement):
    """Must be able to do X. One mixin, two thin subclasses — the dispatch-side
    and template-side requirement tables — each adding only its own parent FK
    (dispatch or revision) and uniqueness constraint."""

    capability_definition = models.ForeignKey(
        "assets.CapabilityDefinition",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        abstract = True


class AbstractSkillRequirement(AbstractRequirement):
    """Need N people certified in X, at level >= L."""

    skill = models.ForeignKey(
        "dispatching.DispatchSkill",
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = models.PositiveIntegerField(default=1)
    minimum_level = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        abstract = True


class AbstractModelRequirement(AbstractRequirement):
    """Need N units of this model, optionally built to a specific
    configuration template.

    configuration_template is an attribute of the model requirement, not a
    requirement kind of its own — a configuration means nothing without a
    model as its subject (ConfigurationTemplate.model is itself a mandatory
    FK). Two rows for the same model are allowed when they differ only by
    configuration ("1 F350 moving-truck configuration" and "1 F350 towing
    configuration" are two rows, not a model row plus an unrelated
    configuration-template row) — see the uniqueness constraint on the two
    concrete subclasses and dispatching_starter_kit/1_dispatch_templates.md.
    """

    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.PROTECT,
        related_name="+",
    )
    configuration_template = models.ForeignKey(
        "assets.ConfigurationTemplate",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Optional. Must belong to the same model as this row.",
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True


class AbstractModificationRequirement(AbstractRequirement):
    """Must have X fitted."""

    defined_modification = models.ForeignKey(
        "assets.DefinedModification",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        abstract = True
