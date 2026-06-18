"""The explicit extension registry.

The single place that knows the full set of extensions. Discovery is an **explicit
list** — not import-time self-registration — so the extension set is greppable and
the D1 "explicit over magical" principle holds. Adding an extension = add its
descriptor class to ``_EXTENSION_CLASSES``.

The registry also performs a startup manifest-validation pass (E5): every registered
extension must declare a well-formed ``ExtensionManifest``.
"""

from __future__ import annotations

from app.detail_extensions.base.extension_descriptor import DetailExtension, ExtensionTarget
from app.detail_extensions.emissions_info.extension import EmissionsInfoExtension
from app.detail_extensions.model_info.extension import ModelInfoExtension
from app.detail_extensions.purchase_info.extension import PurchaseInfoExtension
from app.detail_extensions.smog_record.extension import SmogRecordExtension
from app.detail_extensions.vehicle_registration.extension import VehicleRegistrationExtension

# The full first-party extension set. Order is irrelevant (keys are unique).
_EXTENSION_CLASSES: list[type[DetailExtension]] = [
    PurchaseInfoExtension,
    VehicleRegistrationExtension,
    SmogRecordExtension,
    ModelInfoExtension,
    EmissionsInfoExtension,
]

EXTENSION_REGISTRY: dict[str, type[DetailExtension]] = {
    e.key: e for e in _EXTENSION_CLASSES
}


def get(extension_key: str) -> "type[DetailExtension] | None":
    """Return the descriptor for ``extension_key`` or None."""
    return EXTENSION_REGISTRY.get(extension_key)


def descriptors_for_target(target: ExtensionTarget) -> list[type[DetailExtension]]:
    """All registered descriptors whose target matches."""
    return [e for e in EXTENSION_REGISTRY.values() if e.target is target]
