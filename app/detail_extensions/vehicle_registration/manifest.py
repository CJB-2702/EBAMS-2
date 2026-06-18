from app.detail_extensions.base.manifest import ExtensionManifest

VEHICLE_REGISTRATION_MANIFEST = ExtensionManifest(
    models_module="app.detail_extensions.vehicle_registration.models",
    control_modules=[],
    template_dir=None,
    entrypoints_module=None,
    urls_module=None,
)
