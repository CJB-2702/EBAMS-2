from django.db import models


class ApplicabilityMode(models.TextChoices):
    """How an item's class/model allow-lists gate where it may be applied.

    Shared by DefinedModification (Phase 1) and ConfigurationTemplate (Phase 2).
    The full truth table lives in the kit's
    ``modification_class_and_model_matrix_behaviors.md`` — this enum is only the
    label, the binding logic lives in ``ApplicabilityPolicy``.

    - STRICT       — class AND model both enforced (AND combine; dead-model guard).
    - CLASS_ONLY   — class enforced; model list is a non-binding search hint.
    - MODEL_SET    — model enforced; class list is system-derived from the models.
    - UNRESTRICTED — applies anywhere; both lists are pure suggestions.
    """

    STRICT = "strict", "Class and model"
    CLASS_ONLY = "class_only", "Class only"
    MODEL_SET = "model_set", "Model set"
    UNRESTRICTED = "unrestricted", "Unrestricted"
