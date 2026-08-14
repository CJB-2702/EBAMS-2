"""The price-observation wave (price_observation_mini_kit/, D79-D92). Owned
exclusively by this wave, mirroring urls_demands.py's shape.
"""

from django.urls import path

from app.procurement.presentation_layer.entrypoints.prices import (
    part_price_history,
    price_bulk_grid,
    price_hub,
    unpriced_parts,
)

urlpatterns = [
    path("", price_hub, name="price_hub"),
    path("bulk/", price_bulk_grid, name="price_bulk_grid"),
    path("unpriced/", unpriced_parts, name="unpriced_parts"),
    path("parts/<int:part_id>/", part_price_history, name="part_price_history"),
]
