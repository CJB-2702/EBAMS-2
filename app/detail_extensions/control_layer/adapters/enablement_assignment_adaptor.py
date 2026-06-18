"""AssignmentAdaptor — maps POST payload to structured assign/unassign calls.

The adaptor is the only place that knows the form field naming convention.
It produces a list of ``AssignmentToggle`` structs that the entrypoint passes
directly to ``EnablementManager`` verbs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import QueryDict


@dataclass(frozen=True)
class AssignmentToggle:
    """One on/off switch derived from the POST payload."""

    extension_key: str
    scope: str          # "class" | "model" | "model_ext_class"
    scope_id: int
    enabled: bool       # True → assign, False → unassign


class AssignmentAdaptor:
    """Parse the assignment editor's POST body into structured toggles.

    Form field convention (checkbox grid):
      ``asset_class_<class_id>_<extension_key>``   → ASSET-target on class
      ``model_<model_id>_<extension_key>``           → ASSET-target on model
      ``model_ext_class_<class_id>_<extension_key>``  → MODEL-target on class

    A checkbox present in POST = enabled; absent = disabled.
    The current set of possible keys is passed in so absent ones produce
    explicit ``enabled=False`` toggles rather than being silently skipped.
    """

    @staticmethod
    def parse(
        post: "QueryDict",
        *,
        asset_class_ids: list[int],
        model_ids: list[int],
        asset_extension_keys: list[str],
        model_extension_keys: list[str],
    ) -> list[AssignmentToggle]:
        toggles: list[AssignmentToggle] = []

        for class_id in asset_class_ids:
            for key in asset_extension_keys:
                field = f"asset_class_{class_id}_{key}"
                enabled = field in post
                toggles.append(
                    AssignmentToggle(
                        extension_key=key,
                        scope="class",
                        scope_id=class_id,
                        enabled=enabled,
                    )
                )

        for model_id in model_ids:
            for key in asset_extension_keys:
                field = f"model_{model_id}_{key}"
                enabled = field in post
                toggles.append(
                    AssignmentToggle(
                        extension_key=key,
                        scope="model",
                        scope_id=model_id,
                        enabled=enabled,
                    )
                )

        for class_id in asset_class_ids:
            for key in model_extension_keys:
                field = f"model_ext_class_{class_id}_{key}"
                enabled = field in post
                toggles.append(
                    AssignmentToggle(
                        extension_key=key,
                        scope="model_ext_class",
                        scope_id=class_id,
                        enabled=enabled,
                    )
                )

        return toggles
