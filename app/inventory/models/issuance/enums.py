from django.db import models


class IssueType(models.TextChoices):
    """How this PartIssue row is anchored (Phase 6, FD-5). FOR_PART_DEMAND is
    the original, still-default shape; the other two skip procurement
    entirely (`PartIssuanceOrchestrator` never calls `record_issuance()` for
    them).

    The issuance portal deliberately offers only FOR_PART_DEMAND. The other
    two remain on `PartIssue` because the orchestrator supports them and a
    later kit will surface them; no UI reaches them today.
    """

    FOR_PART_DEMAND = "for_part_demand", "Fulfill Part Demand"
    DIRECT_TO_ASSET = "direct_to_asset", "Direct Issue to Asset"
    DIRECT_TO_USER = "direct_to_user", "Direct Issue to User"


class IssueReason(models.TextChoices):
    """Why material left the storeroom.

    Replaces the free-text `issue_reason` CharField: every reporting question
    of the form "what did we consume on corrective work last quarter" dies on
    free text. The detail people used to type here lives in
    `PartIssueSession.issue_reason_detail` beside this.
    """

    SCHEDULED_MAINTENANCE = "scheduled_maintenance", "Scheduled Maintenance"
    CORRECTIVE_REPAIR = "corrective_repair", "Corrective Repair"
    FIELD_REPAIR = "field_repair", "Field Repair"
    BUILD_OR_KITTING = "build_or_kitting", "Build / Kitting"
    WARRANTY = "warranty", "Warranty Work"
    CONSUMABLE_RESTOCK = "consumable_restock", "Consumable Restock"
    OTHER = "other", "Other"
