"""Adaptor: the single source for XYZ coordinate formatting (FD-16).

Everything that touches a storage-location coordinate — the topography
factories/managers, movement forms, and the Phase 3 SVG shape matcher —
imports `format_xyz_coordinate` / `build_display_code` from here rather than
restating the zero-pad rule.
"""

from __future__ import annotations

from app.inventory.control_layer.constants import COORDINATE_PAD_WIDTH


def format_xyz_coordinate(value: str) -> str:
    """4-digit zero-pads numeric coordinate input; never truncates longer or
    non-numeric input (part_movements.md §2).

        "10"          -> "0010"
        "12345"       -> "12345"     (already >= 4 digits, unchanged)
        "AISLE-A12"   -> "AISLE-A12" (non-numeric, unchanged)
    """
    if not value:
        return ""
    clean_val = str(value).strip()
    if clean_val.isdigit():
        if len(clean_val) < COORDINATE_PAD_WIDTH:
            return clean_val.zfill(COORDINATE_PAD_WIDTH)
        return clean_val
    return clean_val


def build_room_location_display_code(major_coord: str, minor_coord: str) -> str:
    """`"X-Y"` from already-formatted coordinate parts — `RoomLocation.display_code`."""
    return f"{major_coord}-{minor_coord}"


def build_storage_location_display_code(
    room_location_display_code: str, atomic_coord: str
) -> str:
    """`"X-Y-Z"` — the full 3-segment `StorageLocation.display_code`, composed
    from its parent `RoomLocation.display_code` plus the atomic coordinate
    (FD-29: major/minor live only on `RoomLocation`)."""
    return f"{room_location_display_code}-{atomic_coord}"
