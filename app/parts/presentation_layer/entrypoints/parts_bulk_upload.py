"""Bulk parts upload — paste-from-Excel grid at /parts/bulk-upload/."""

from __future__ import annotations

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.parts.control_layer.adapters.part_bulk_upload_adaptor import (
    PartBulkUploadAdaptor,
)
from app.parts.control_layer.factories.part_bulk_upload_factory import (
    PartBulkUploadFactory,
)
from app.procurement.presentation_layer.tools.recent_part_creations import (
    record_created_parts,
)


@require_http_methods(["GET", "POST"])
def part_bulk_upload(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        rows = PartBulkUploadAdaptor.from_post(request.POST)
        domain_ids = PartBulkUploadAdaptor.domain_ids_from_post(request.POST)
        results = PartBulkUploadFactory.create_many(rows=rows, actor=request.user, domain_ids=domain_ids)
        succeeded = [r for r in results if r.ok]
        failed = [r for r in results if not r.ok]
        # DELIBERATE ANTI-PATTERN (D81) — see recent_part_creations.py.
        part_ids = [r.part_id for r in succeeded]
        domain_ids_by_part = {part_id: domain_ids for part_id in part_ids}
        transaction.on_commit(
            lambda: record_created_parts(
                request, part_ids=part_ids, domain_ids_by_part=domain_ids_by_part
            )
        )
        return render(
            request,
            "parts/bulk_upload.html",
            {"results": results, "succeeded": succeeded, "failed": failed, "submitted": True},
        )
    return render(
        request,
        "parts/bulk_upload.html",
        {"submitted": False, "domains": Domain.objects.order_by("name")},
    )
