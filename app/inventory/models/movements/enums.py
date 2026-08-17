from django.db import models


class MovementType(models.TextChoices):
    """Classified by `MovementManager.classify` from source/destination shape
    — never chosen directly by a caller (part_movements.md §1).

    CYCLE_COUNT_ADJUSTMENT is reserved for the Phase 7 audit build; nothing in
    Phase 6 writes it.
    """

    PUTAWAY = "putaway", "Putaway from Intake Room"
    INTER_ROOM = "inter_room", "Inter-Room Transfer"
    INTER_WAREHOUSE = "inter_warehouse", "Inter-Warehouse Transfer"
    BIN_ADJUSTMENT = "bin_adjustment", "Bin Adjustment"
    CYCLE_COUNT_ADJUSTMENT = "cycle_count_adjustment", "Cycle Count Adjustment"
