from app.detail_extensions.base.manifest import ExtensionManifest

EMISSIONS_INFO_MANIFEST = ExtensionManifest(
    models_module="app.detail_extensions.emissions_info.models",
    control_modules=[],
    template_dir=None,
    entrypoints_module=None,
    urls_module=None,
)
