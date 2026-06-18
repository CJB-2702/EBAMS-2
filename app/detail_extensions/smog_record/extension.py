from app.detail_extensions.base.extension_descriptor import (
    DetailExtension,
    ExtensionCardinality,
    ExtensionTarget,
)
from app.detail_extensions.smog_record.manifest import SMOG_RECORD_MANIFEST
from app.detail_extensions.smog_record.models import SmogRecord


class SmogRecordExtension(DetailExtension):
    key = "smog_record"
    label = "Smog Test History"
    target = ExtensionTarget.ASSET
    # History of tests — the reference one-to-many extension.
    cardinality = ExtensionCardinality.ONE_TO_MANY
    primary_model = SmogRecord
    manifest = SMOG_RECORD_MANIFEST
