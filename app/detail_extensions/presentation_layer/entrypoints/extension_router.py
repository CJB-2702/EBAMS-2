"""Extension router — framework dispatcher for per-extension URL slots.

Validates <extension-key>, derives target-typed segments from the descriptor,
checks enablement, and dispatches to the extension's declared entrypoint module
(or a shared placeholder when the body is not yet implemented).

Route grammar (E6):
  /<extension-key>/                            → summary/index (slot)
  /<extension-key>/<assets|models>/            → search (slot)
  /<extension-key>/<asset|model>/<id>/         → owner detail (slot)
  /<extension-key>/<asset|model>/<id>/<row>/   → single row  (slot)
"""

from __future__ import annotations

import importlib

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.detail_extensions import registry
from app.detail_extensions.base.extension_descriptor import ExtensionTarget
from app.detail_extensions.control_layer.domain_structs.owner_enablement_struct import (
    OwnerEnablementStruct,
)
from app.detail_extensions.control_layer.guards.extension_registry_guard import (
    ExtensionRegistryValidator,
    UnknownExtensionError,
)
from app.detail_extensions.models.enablement import (
    DetailExtensionsByAssetClass,
    DetailExtensionsByModel,
    ModelDetailExtensionsByAssetClass,
)


def _resolve_descriptor_or_404(extension_key: str):
    try:
        return ExtensionRegistryValidator.resolve(extension_key)
    except UnknownExtensionError:
        raise Http404(f"Unknown extension: {extension_key!r}")


def _expected_singular(descriptor) -> str:
    return "asset" if descriptor.target is ExtensionTarget.ASSET else "model"


def _expected_plural(descriptor) -> str:
    return "assets" if descriptor.target is ExtensionTarget.ASSET else "models"


def _is_enabled_for_owner(descriptor, owner_id: int) -> bool:
    """Whether this extension is enabled for the specific owner (asset/model id).

    Resolves the owner's actual class/model and asks the shared
    ``OwnerEnablementStruct`` — the same resolver the provisioner uses, so the
    router allows exactly what provisioning would create.
    """
    enablement = OwnerEnablementStruct.for_owner_id(
        target=descriptor.target, owner_id=owner_id
    )
    if enablement is None:  # owner row does not exist
        return False
    return enablement.is_enabled(descriptor.key)


def _is_extension_assigned(extension_key: str) -> bool:
    """True if the extension has at least one enablement row (any scope)."""
    return (
        DetailExtensionsByAssetClass.objects.filter(extension_key=extension_key).exists()
        or DetailExtensionsByModel.objects.filter(extension_key=extension_key).exists()
        or ModelDetailExtensionsByAssetClass.objects.filter(extension_key=extension_key).exists()
    )


def _placeholder(request: HttpRequest, **ctx) -> HttpResponse:
    """Shared placeholder rendered for every unimplemented extension slot."""
    return render(request, "detail_extensions/slot_placeholder.html", ctx)


def _dispatch(request: HttpRequest, descriptor, slot: str, **ctx) -> HttpResponse:
    """Try to dispatch to the extension's declared entrypoint; fall back to placeholder."""
    manifest = descriptor.manifest
    if manifest and manifest.entrypoints_module:
        try:
            mod = importlib.import_module(manifest.entrypoints_module)
            handler = getattr(mod, slot, None)
            if callable(handler):
                return handler(request, **ctx)
        except ImportError:
            pass
    return _placeholder(request, descriptor=descriptor, slot=slot, **ctx)


@require_http_methods(["GET"])
def summary(request: HttpRequest, extension_key: str) -> HttpResponse:
    descriptor = _resolve_descriptor_or_404(extension_key)
    if not _is_extension_assigned(extension_key):
        raise Http404(f"Extension '{extension_key}' is not enabled.")
    return _dispatch(request, descriptor, "summary", extension_key=extension_key)


@require_http_methods(["GET"])
def search(request: HttpRequest, extension_key: str, collection: str) -> HttpResponse:
    descriptor = _resolve_descriptor_or_404(extension_key)
    expected = _expected_plural(descriptor)
    if collection != expected:
        raise Http404(
            f"Extension '{extension_key}' uses '{expected}' (not '{collection}')."
        )
    if not _is_extension_assigned(extension_key):
        raise Http404(f"Extension '{extension_key}' is not enabled.")
    return _dispatch(
        request, descriptor, "search",
        extension_key=extension_key, collection=collection,
    )


@require_http_methods(["GET", "POST"])
def owner_detail(
    request: HttpRequest,
    extension_key: str,
    owner_type: str,
    owner_id: int,
) -> HttpResponse:
    descriptor = _resolve_descriptor_or_404(extension_key)
    expected = _expected_singular(descriptor)
    if owner_type != expected:
        raise Http404(
            f"Extension '{extension_key}' uses '{expected}' (not '{owner_type}')."
        )
    if not _is_enabled_for_owner(descriptor, owner_id):
        raise Http404(
            f"Extension '{extension_key}' is not enabled for {owner_type} {owner_id}."
        )
    return _dispatch(
        request, descriptor, "owner_detail",
        extension_key=extension_key, owner_type=owner_type, owner_id=owner_id,
    )


@require_http_methods(["GET", "POST"])
def single_row(
    request: HttpRequest,
    extension_key: str,
    owner_type: str,
    owner_id: int,
    row_id: int,
) -> HttpResponse:
    descriptor = _resolve_descriptor_or_404(extension_key)
    expected = _expected_singular(descriptor)
    if owner_type != expected:
        raise Http404(
            f"Extension '{extension_key}' uses '{expected}' (not '{owner_type}')."
        )
    # ONE_TO_ONE extensions terminate at owner_detail; row_id is only valid for ONE_TO_MANY.
    from app.detail_extensions.base.extension_descriptor import ExtensionCardinality
    if descriptor.cardinality is ExtensionCardinality.ONE_TO_ONE:
        raise Http404(
            f"Extension '{extension_key}' is one-to-one; there is no single-row slot."
        )
    if not _is_enabled_for_owner(descriptor, owner_id):
        raise Http404(
            f"Extension '{extension_key}' is not enabled for {owner_type} {owner_id}."
        )
    return _dispatch(
        request, descriptor, "single_row",
        extension_key=extension_key, owner_type=owner_type,
        owner_id=owner_id, row_id=row_id,
    )
