from django.urls import path

from app.parts.presentation_layer.entrypoints.manufacturers import (
    manufacturer_create,
    manufacturer_index,
)
from app.parts.presentation_layer.entrypoints.library import (
    library_add_document,
    library_remove_document,
    part_library,
)
from app.parts.presentation_layer.entrypoints.parts import (
    part_add_comment,
    part_add_gallery_image,
    part_create,
    part_detail,
    part_edit,
    part_remove_gallery_image,
    part_set_primary_image,
    parts_hub,
)
from app.parts.presentation_layer.entrypoints.revisions import (
    part_revisions,
    revision_add_comment,
    revision_attach_document,
    revision_detail,
    revision_detail_by_id,
    revision_set_status,
)
from app.parts.presentation_layer.entrypoints.search import part_search
from app.parts.presentation_layer.entrypoints.supplier_items import (
    part_supplier_items,
    supplier_item_add_comment,
    supplier_item_create,
    supplier_item_detail,
    supplier_item_log_vendor_revision,
)

urlpatterns = [
    # Hub & search
    path("", parts_hub, name="parts_hub"),
    path("search/", part_search, name="part_search"),

    # Parts
    path("new/", part_create, name="part_create"),
    path("<int:part_id>/", part_detail, name="part_detail"),
    path("<int:part_id>/edit/", part_edit, name="part_edit"),
    path("<int:part_id>/comments/", part_add_comment, name="part_add_comment"),
    path("<int:part_id>/gallery/", part_add_gallery_image, name="part_add_gallery_image"),
    path("<int:part_id>/gallery/remove/", part_remove_gallery_image, name="part_remove_gallery_image"),
    path("<int:part_id>/gallery/primary/", part_set_primary_image, name="part_set_primary_image"),

    # Library (technical document store)
    path("<int:part_id>/library/", part_library, name="part_library"),
    path("<int:part_id>/library/add/", library_add_document, name="library_add_document"),
    path("<int:part_id>/library/remove/", library_remove_document, name="library_remove_document"),

    # Revisions
    path("<int:part_id>/revisions/", part_revisions, name="part_revisions"),
    path(
        "<int:part_id>/revisions/<int:revision_id>/",
        revision_detail,
        name="revision_detail",
    ),
    path(
        "revisions/<int:revision_id>/",
        revision_detail_by_id,
        name="revision_detail_by_id",
    ),
    path(
        "<int:part_id>/revisions/<int:revision_id>/status/",
        revision_set_status,
        name="revision_set_status",
    ),
    path(
        "<int:part_id>/revisions/<int:revision_id>/documents/",
        revision_attach_document,
        name="revision_attach_document",
    ),
    path(
        "<int:part_id>/revisions/<int:revision_id>/comments/",
        revision_add_comment,
        name="revision_add_comment",
    ),

    # Manufacturers
    path("manufacturers/", manufacturer_index, name="part_manufacturer_index"),
    path("manufacturers/create/", manufacturer_create, name="part_manufacturer_create"),

    # Supplier items
    path("<int:part_id>/supplier-items/", part_supplier_items, name="part_supplier_items"),
    path("<int:part_id>/supplier-items/new/", supplier_item_create, name="supplier_item_create"),
    path("supplier-items/<int:item_id>/", supplier_item_detail, name="supplier_item_detail"),
    path(
        "supplier-items/<int:item_id>/vendor-revisions/",
        supplier_item_log_vendor_revision,
        name="supplier_item_log_vendor_revision",
    ),
    path(
        "supplier-items/<int:item_id>/comments/",
        supplier_item_add_comment,
        name="supplier_item_add_comment",
    ),
]
