from django.db import models


class IssueType(models.TextChoices):
    """How this PartIssue row is anchored (Phase 6, FD-5). FOR_PART_DEMAND is
    the original, still-default shape; the other two skip procurement
    entirely (`PartIssuanceOrchestrator` never calls `record_issuance()` for
    them)."""

    FOR_PART_DEMAND = "for_part_demand", "Fulfill Part Demand"
    DIRECT_TO_ASSET = "direct_to_asset", "Direct Issue to Asset"
    DIRECT_TO_USER = "direct_to_user", "Direct Issue to User"


class IssueSessionStatus(models.TextChoices):
    DRAFT = "draft", "Draft / Staged"
    COMMITTED = "committed", "Committed"
    CANCELLED = "cancelled", "Cancelled"

