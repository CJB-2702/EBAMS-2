"""Shared numeric and status constants for the inventory control layer.

One source so quantity/coordinate rules are never re-declared as literals
across factories, managers, and guards (FD-8, FD-16).
"""

from __future__ import annotations

#: Decimal shape for every quantity/cost column in inventory (FD-8).
DECIMAL_PLACES = 3
MAX_DIGITS = 12

#: XYZ coordinate padding width (part_movements.md §2).
COORDINATE_PAD_WIDTH = 4

#: Max accepted SVG layout upload size, both spatial-engine tiers (FD-25/29).
MAX_SVG_UPLOAD_BYTES = 2 * 1024 * 1024

#: Inkscape layer-group labels the adapter looks for shapes under, per tier.
ROOM_SVG_GROUP_LABEL = "locations"
ROOM_LOCATION_SVG_GROUP_LABEL = "bins"
