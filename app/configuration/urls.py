"""Configuration Management URL routes.

This app currently owns **only** the serialized-part placeholder routes. The
live configuration and capability pages are still routed by
``app/assets/urls.py`` under ``/assets/`` — they merely render inside this
section's shell (``configuration/base.html``). See
``docs/assets/tech_debt/configuration_section_extraction.md`` for the plan to
move those routes here.
"""

from django.urls import path

from app.configuration.presentation_layer.entrypoints.serialized_parts import (
    serialized_part_history_index,
    serialized_part_template_index,
)

urlpatterns = [
    # Serialized parts (placeholders)
    path(
        "serialized-parts/templates/",
        serialized_part_template_index,
        name="serialized_part_template_index",
    ),
    path(
        "serialized-parts/history/",
        serialized_part_history_index,
        name="serialized_part_history_index",
    ),
]
