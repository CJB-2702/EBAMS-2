"""Revision workbench — append, set status, attach documents. Engineer work portal."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.parts.control_layer.adapters.revision_append_adaptor import (
    RevisionAppendAdaptor,
)
from app.parts.control_layer.adapters.revision_edit_adaptor import RevisionEditAdaptor
from app.parts.control_layer.domain_structs.part_structs.part_revision_history_struct import (
    PartRevisionHistoryStruct,
)
from app.parts.control_layer.domain_structs.reverse_structs.part_revision_struct import (
    PartRevisionNotFoundError,
    PartRevisionStruct,
)
from app.events.control_layer.managers.activity_thread_manager import ActivityThreadManager
from app.events.models import ActivityThread
from app.parts.control_layer.part_context import PartContext
from app.parts.control_layer.thread_domain import default_domain_id_for
from app.utils.safe_redirect import safe_next_url

PART_REVISION_MANAGE_PERM = "parts.change_partrevision"


@require_http_methods(["GET", "POST"])
def part_revisions(request: HttpRequest, part_id: int) -> HttpResponse:
    ctx = PartContext(part_id, actor=request.user)
    if request.method == "POST":
        data = RevisionAppendAdaptor.from_post(request.POST)
        manager = ctx.revisions_manager
        if data["kind"] == "redline":
            manager.redline(
                major_number=data["major_number"],
                minor_name=data["minor_name"],
                summary=data["summary"],
                date_of_release=data["date_of_release"],
            )
        else:
            manager.release_major(
                summary=data["summary"],
                major_name=data["major_name"],
                date_of_release=data["date_of_release"],
            )
        messages.success(request, "Revision added.")
        return redirect(reverse("part_revisions", kwargs={"part_id": part_id}))
    revisions = PartRevisionHistoryStruct.from_id(part_id, eager_thread=True).to_dict()
    return render(
        request,
        "parts/revisions/workbench.html",
        {
            "part": ctx.struct().to_dict(),
            "part_id": part_id,
            "revisions": revisions,
            "domains": Domain.objects.order_by("name"),
            "can_manage": request.user.has_perm(PART_REVISION_MANAGE_PERM),
        },
    )


@require_http_methods(["POST"])
def revision_set_status(request: HttpRequest, part_id: int, revision_id: int) -> HttpResponse:
    ctx = PartContext(part_id, actor=request.user)
    status = request.POST.get("status", "")
    ctx.revisions_manager.set_status(revision_id, status)
    messages.success(request, "Revision status updated.")
    return redirect(reverse("part_revisions", kwargs={"part_id": part_id}))


def _revision_edit(request: HttpRequest, part_id: int, revision_id: int) -> HttpResponse:
    if not request.user.has_perm(PART_REVISION_MANAGE_PERM):
        return HttpResponseForbidden("You may not edit this revision.")
    try:
        struct = PartRevisionStruct(revision_id)
    except PartRevisionNotFoundError:
        raise Http404
    ctx = PartContext(part_id, actor=request.user)

    if request.method == "POST":
        data = RevisionEditAdaptor.from_post(request.POST)
        ctx.revisions_manager.update(revision_id, data=data)
        messages.success(request, "Revision updated.")
        return redirect(reverse("part_revisions", kwargs={"part_id": part_id}))

    return render(
        request,
        "parts/revisions/edit.html",
        {"part_id": part_id, "revision": struct.to_dict()},
    )


@require_http_methods(["GET", "POST"])
def revision_edit(request: HttpRequest, revision_id: int) -> HttpResponse:
    try:
        struct = PartRevisionStruct(revision_id)
    except PartRevisionNotFoundError:
        raise Http404
    return _revision_edit(request, struct.revision.part_id, revision_id)


@require_http_methods(["GET", "POST"])
def revision_edit_by_slug(request: HttpRequest, part_id: int, revision_slug: str) -> HttpResponse:
    from app.parts.models import PartRevision

    try:
        major_str, minor_str = revision_slug.rsplit("-", 1)
        major, minor = int(major_str), int(minor_str)
    except ValueError:
        raise Http404
    try:
        revision = PartRevision.objects.get(
            part_id=part_id, major_revision_number=major, minor_revision_number=minor
        )
    except PartRevision.DoesNotExist:
        raise Http404
    return _revision_edit(request, part_id, revision.id)


@require_http_methods(["GET"])
def revision_detail(request: HttpRequest, part_id: int, revision_id: int) -> HttpResponse:
    try:
        struct = PartRevisionStruct(revision_id)
    except PartRevisionNotFoundError:
        raise Http404
    return render(
        request,
        "parts/revisions/detail.html",
        {"part_id": part_id, "revision": struct.to_dict()},
    )


@require_http_methods(["GET"])
def revision_detail_by_id(request: HttpRequest, revision_id: int) -> HttpResponse:
    try:
        struct = PartRevisionStruct(revision_id)
    except PartRevisionNotFoundError:
        raise Http404
    part_id = struct.revision.part_id
    return render(
        request,
        "parts/revisions/detail.html",
        {"part_id": part_id, "revision": struct.to_dict()},
    )


@require_http_methods(["POST"])
def revision_add_comment(request: HttpRequest, part_id: int, revision_id: int) -> HttpResponse:
    from app.parts.models import PartRevision

    revision = PartRevision.objects.get(id=revision_id, part_id=part_id)
    body = request.POST.get("content", "").strip()
    if body:
        ActivityThreadManager(
            revision,
            request.user,
            domain_id_resolver=lambda: default_domain_id_for(ActivityThread),
        ).add_comment(body)
        messages.success(request, "Comment added.")
    return redirect(safe_next_url(request, reverse("part_revisions", kwargs={"part_id": part_id})))


@require_http_methods(["POST"])
def revision_attach_document(request: HttpRequest, part_id: int, revision_id: int) -> HttpResponse:
    from app.parts.models import PartRevision

    revision = PartRevision.objects.get(id=revision_id, part_id=part_id)
    uploaded = request.FILES.get("file")
    domain_id = request.POST.get("domain")
    if uploaded and domain_id:
        result = ActivityThreadManager(revision, request.user).attach_document(
            uploaded, domain_id=int(domain_id), caption=request.POST.get("caption", "")
        )
        if result.ok:
            messages.success(request, "Document attached.")
        else:
            for error in result.errors:
                messages.error(request, error)
    return redirect(
        reverse("revision_detail", kwargs={"part_id": part_id, "revision_id": revision_id})
    )
