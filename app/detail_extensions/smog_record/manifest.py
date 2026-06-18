from app.detail_extensions.base.manifest import ExtensionManifest

SMOG_RECORD_MANIFEST = ExtensionManifest(
    models_module="app.detail_extensions.smog_record.models",
    control_modules=[],
    template_dir=None,
    entrypoints_module=None,
    urls_module=None,
)
