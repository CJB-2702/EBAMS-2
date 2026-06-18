"""Configuration entrypoints — enablement CRUD UI.

Thin entrypoints only: parse → call manager verb → redirect/render.
No writes happen here; all writes go through EnablementManager.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.detail_extensions.control_layer.adapters.enablement_assignment_adaptor import (
    AssignmentAdaptor,
)
from app.detail_extensions.control_layer.enablement_manager import EnablementManager
from app.detail_extensions.control_layer.guards.enablement_assignment_guard import (
    AssignmentPermissionDenied,
    AssignmentValidationError,
)
from app.detail_extensions.control_layer.guards.extension_registry_guard import (
    UnknownExtensionError,
)
from app.detail_extensions.presentation_layer.search.enablement_search import (
    get_assign_editor_context,
    get_catalog,
)
from app.detail_extensions.base.extension_descriptor import ExtensionTarget
from app.detail_extensions import registry


@require_http_methods(["GET"])
def landing(request: HttpRequest) -> HttpResponse:
    catalog = get_catalog()
    return render(
        request,
        "detail_extensions/configuration/landing.html",
        {"catalog": catalog},
    )


@require_http_methods(["GET", "POST"])
def assign_editor(request: HttpRequest, extension_key: str) -> HttpResponse:
    try:
        ctx = get_assign_editor_context(extension_key)
    except UnknownExtensionError:
        raise Http404(f"Unknown extension key: {extension_key!r}")

    if request.method == "POST":
        asset_extension_keys = [
            e.key for e in registry.EXTENSION_REGISTRY.values()
            if e.target is ExtensionTarget.ASSET
        ]
        model_extension_keys = [
            e.key for e in registry.EXTENSION_REGISTRY.values()
            if e.target is ExtensionTarget.MODEL
        ]
        toggles = AssignmentAdaptor.parse(
            request.POST,
            asset_class_ids=[c.id for c in ctx.asset_classes],
            model_ids=[m.id for m in ctx.asset_models],
            asset_extension_keys=asset_extension_keys,
            model_extension_keys=model_extension_keys,
        )

        # Only process toggles relevant to this extension_key.
        relevant = [t for t in toggles if t.extension_key == extension_key]

        try:
            for toggle in relevant:
                if toggle.scope == "class":
                    if toggle.enabled:
                        EnablementManager.assign_to_class(
                            extension_key=toggle.extension_key,
                            asset_class_id=toggle.scope_id,
                            actor=request.user,
                        )
                    else:
                        EnablementManager.unassign_from_class(
                            extension_key=toggle.extension_key,
                            asset_class_id=toggle.scope_id,
                            actor=request.user,
                        )
                elif toggle.scope == "model":
                    if toggle.enabled:
                        EnablementManager.assign_to_model(
                            extension_key=toggle.extension_key,
                            model_id=toggle.scope_id,
                            actor=request.user,
                        )
                    else:
                        EnablementManager.unassign_from_model(
                            extension_key=toggle.extension_key,
                            model_id=toggle.scope_id,
                            actor=request.user,
                        )
                elif toggle.scope == "model_ext_class":
                    if toggle.enabled:
                        EnablementManager.assign_model_ext_to_class(
                            extension_key=toggle.extension_key,
                            asset_class_id=toggle.scope_id,
                            actor=request.user,
                        )
                    else:
                        EnablementManager.unassign_model_ext_from_class(
                            extension_key=toggle.extension_key,
                            asset_class_id=toggle.scope_id,
                            actor=request.user,
                        )
        except AssignmentPermissionDenied as exc:
            messages.error(request, str(exc))
            return redirect(
                reverse("extension_assign_editor", kwargs={"extension_key": extension_key})
            )
        except AssignmentValidationError as exc:
            messages.error(request, str(exc))
            return redirect(
                reverse("extension_assign_editor", kwargs={"extension_key": extension_key})
            )

        messages.success(
            request,
            f"Extension '{ctx.descriptor.label}' assignment updated.",
        )
        return redirect(
            reverse("extension_assign_editor", kwargs={"extension_key": extension_key})
        )

    # GET
    return render(
        request,
        "detail_extensions/configuration/assign_editor.html",
        {"ctx": ctx},
    )
