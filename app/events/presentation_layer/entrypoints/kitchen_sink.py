"""
Kitchen-sink display page — renders the reusable card fragments
(events/fragments/{comments,gallery,files}_card.html) against real sample data.
Section 1 (composite activity thread) and section 2 (comments only) share the
exact same `activity_card` context and the exact same comments_card.html
fragment, so there is only one comments implementation to keep in sync.

A Part's documents and gallery each live on their *own* underlying thread row
(see PartContext.documents_thread / .gallery), so sections 3 & 4 independently
pick whichever thread is richest for what they're demonstrating.

Read-only reference page. Not linked into any workflow.
"""

from __future__ import annotations

from collections import Counter

from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.events.control_layer.domain_structs.event_detail_struct import EventDetailStruct
from app.events.models import Attachment, Event
from app.events.presentation_layer.tools.file_previews import build_comments_context
from app.events.presentation_layer.tools.generic_cards import document_dict
from app.utils.hashids import encode_id


@require_http_methods(["GET"])
def kitchen_sink(request: HttpRequest) -> HttpResponse:
    # ── Section 1 source: a real business Event (thread_type=event) ──
    # Event.objects (not Event.threads) excludes the generic ActivityThread rows
    # Part/SupplierItem hang their own comment/document threads off (same table,
    # sentinel-valued fields) — event_card.html renders event-specific fields
    # that are meaningless on those rows.
    sample_event = (
        Event.objects.active()
        .select_related("domain", "created_by")
        .annotate(
            human_comment_count=Count(
                "comments",
                filter=Q(comments__is_human_made=True, comments__deleted_at__isnull=True),
                distinct=True,
            )
        )
        .order_by("-human_comment_count")
        .first()
    )
    activity_card = None
    if sample_event is not None:
        event_hash = encode_id(sample_event.pk)
        sample_event_struct = EventDetailStruct(sample_event.pk, include_shadow_comments=True)
        activity_card = {
            "event": sample_event,
            "hash": event_hash,
            "comments": build_comments_context(sample_event_struct),
            "direct_attachments": [
                document_dict(a) for a in sample_event_struct.standalone_attachments
            ],
        }

    # ── Sections 3 & 4 source: whichever thread has the most standalone image /
    # non-image attachments respectively (e.g. a Part's gallery_thread vs its
    # documents_thread — distinct rows, so picked independently). ──
    standalone = list(
        Attachment.objects.filter(deleted_at__isnull=True, comment_id__isnull=True)
        .select_related("file")
        .filter(file__deleted_at__isnull=True)
    )
    image_counts = Counter(a.thread_id for a in standalone if a.file.is_image())
    file_counts = Counter(a.thread_id for a in standalone if not a.file.is_image())

    gallery_images = []
    if image_counts:
        gallery_thread_id = image_counts.most_common(1)[0][0]
        gallery_images = [
            document_dict(a) for a in standalone
            if a.thread_id == gallery_thread_id and a.file.is_image()
        ]

    file_documents = []
    if file_counts:
        files_thread_id = file_counts.most_common(1)[0][0]
        file_documents = [
            document_dict(a) for a in standalone
            if a.thread_id == files_thread_id and not a.file.is_image()
        ]

    return render(request, "events/kitchen_sink.html", {
        "sample_event": sample_event,
        "activity_card": activity_card,
        "gallery_images": gallery_images,
        "file_documents": file_documents,
    })
