from app.detail_extensions.base.extension_descriptor import (
    DetailExtension,
    ExtensionCardinality,
    ExtensionTarget,
)
from app.detail_extensions.vehicle_registration.manifest import VEHICLE_REGISTRATION_MANIFEST
from app.detail_extensions.vehicle_registration.models import VehicleRegistration


class VehicleRegistrationExtension(DetailExtension):
    key = "vehicle_registration"
    label = "Vehicle Registration"
    target = ExtensionTarget.ASSET
    # One current registration per asset. Flip to ONE_TO_MANY for a history.
    cardinality = ExtensionCardinality.ONE_TO_ONE
    primary_model = VehicleRegistration
    manifest = VEHICLE_REGISTRATION_MANIFEST
