from app.detail_extensions.base.manifest import ExtensionManifest

MODEL_INFO_MANIFEST = ExtensionManifest(
    models_module="app.detail_extensions.model_info.models",
    control_modules=[],
    template_dir=None,
    entrypoints_module=None,
    urls_module=None,
)
