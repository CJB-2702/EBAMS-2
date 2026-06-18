from app.detail_extensions.base.manifest import ExtensionManifest

PURCHASE_INFO_MANIFEST = ExtensionManifest(
    models_module="app.detail_extensions.purchase_info.models",
    control_modules=[],
    template_dir=None,
    entrypoints_module=None,
    urls_module=None,
)
