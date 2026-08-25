"""
Adapters from events domain objects to the generic card dict contract.

This is the same plain-dict shape app/events/control_layer/managers/activity_thread_manager.py
already produces for its documents()/comments() methods. Any card fragment under
events/fragments/{comments,gallery,files}_card.html is written against this contract,
not against events model objects — so the same fragments can render data sourced from
any sub-application's thread manager, as long as it's shaped into these dicts first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.events.models import Attachment, Comment, Event


def document_dict(attachment: "Attachment") -> dict:
    """Attachment -> generic document dict (gallery_card / files_card contract)."""
    file = attachment.file
    return {
        "id": str(attachment.id),
        "file_id": str(attachment.file_id),
        "filename": file.original_filename,
        "caption": attachment.caption,
        "icon": file.get_icon_class(),
        "is_image": file.is_image(),
        "file_size": file.file_size,
        "created_at": attachment.created_at.isoformat(),
        "created_at_display": attachment.created_at.strftime("%b %d, %Y"),
        "created_by": str(attachment.created_by) if attachment.created_by_id else "—",
    }


def comment_dict(comment: "Comment", attachments: "list[Attachment] | None" = None) -> dict:
    """Comment (+ its attachments) -> generic comment dict (comments_card contract)."""
    return {
        "id": comment.pk,
        "author": str(comment.created_by) if comment.created_by_id else "system",
        "body": comment.content,
        "created_at": comment.created_at,
        "is_human_made": comment.is_human_made,
        "attachments": [document_dict(a) for a in (attachments or [])],
    }


def get_event_header_style(event_type: str) -> dict:
    styles = {
        "maintenance": {
            "bg": "#fffbeb",
            "border": "#f59e0b",
            "text": "#92400e",
            "badge_style": "background-color:#fef3c7; color:#92400e; font-weight:700;",
            "icon": "build",
        },
        "dispatching": {
            "bg": "#eef2ff",
            "border": "#6366f1",
            "text": "#3730a3",
            "badge_style": "background-color:#e0e7ff; color:#3730a3; font-weight:700;",
            "icon": "local_shipping",
        },
        "reservation": {
            "bg": "#f3e8ff",
            "border": "#a855f7",
            "text": "#6b21a8",
            "badge_style": "background-color:#f3e8ff; color:#6b21a8; font-weight:700;",
            "icon": "bookmark",
        },
        "inventory": {
            "bg": "#ecfdf5",
            "border": "#10b981",
            "text": "#047857",
            "badge_style": "background-color:#d1fae5; color:#047857; font-weight:700;",
            "icon": "inventory_2",
        },
        "procurement": {
            "bg": "#f0fdf4",
            "border": "#14b8a6",
            "text": "#0f766e",
            "badge_style": "background-color:#ccfbf1; color:#0f766e; font-weight:700;",
            "icon": "shopping_cart",
        },
        "asset_management": {
            "bg": "#f1f5f9",
            "border": "#64748b",
            "text": "#334155",
            "badge_style": "background-color:#e2e8f0; color:#334155; font-weight:700;",
            "icon": "precision_manufacturing",
        },
        "administration": {
            "bg": "#fff1f2",
            "border": "#f43f5e",
            "text": "#be123c",
            "badge_style": "background-color:#ffe4e6; color:#be123c; font-weight:700;",
            "icon": "admin_panel_settings",
        },
    }
    return styles.get(event_type, {
        "bg": "#f8fafc",
        "border": "#94a3b8",
        "text": "#475569",
        "badge_style": "background-color:#f1f5f9; color:#475569; font-weight:700;",
        "icon": "event",
    })


def get_event_origin_link(thread: "Event", detail: Any, asset_links: list) -> dict | None:
    from django.urls import reverse

    if thread.event_type == "dispatching":
        try:
            return {
                "url": reverse("dispatching_dispatch_detail", kwargs={"pk": thread.pk}),
                "label": f"Dispatch #{thread.pk}",
                "icon": "local_shipping",
            }
        except Exception:
            pass

    if thread.event_type == "reservation":
        try:
            return {
                "url": reverse("dispatching_reservation_detail", kwargs={"pk": thread.pk}),
                "label": f"Reservation #{thread.pk}",
                "icon": "bookmark",
            }
        except Exception:
            pass

    if thread.event_type == "maintenance":
        try:
            return {
                "url": reverse("maintenance_detail", kwargs={"pk": thread.pk}),
                "label": f"Maintenance Action #{thread.pk}",
                "icon": "build",
            }
        except Exception:
            pass

    if detail:
        if hasattr(detail, "asset") and detail.asset:
            try:
                return {
                    "url": reverse("asset_detail", kwargs={"asset_id": detail.asset.pk}),
                    "label": f"Asset: {detail.asset.name}",
                    "icon": "precision_manufacturing",
                }
            except Exception:
                pass

    if asset_links:
        first_asset = asset_links[0].asset
        if first_asset:
            try:
                return {
                    "url": reverse("asset_detail", kwargs={"asset_id": first_asset.pk}),
                    "label": f"Asset: {first_asset.name}",
                    "icon": "precision_manufacturing",
                }
            except Exception:
                pass

    if detail and hasattr(detail, "requested_for") and detail.requested_for:
        user_obj = detail.requested_for
        try:
            return {
                "url": reverse("user_detail", kwargs={"user_id": user_obj.pk}),
                "label": f"User: {user_obj.get_full_name() or user_obj.username}",
                "icon": "person",
            }
        except Exception:
            pass

    return None


def build_activity_card(thread: "Event", user) -> dict:
    """Any activity-thread row (Event, ActivityThread, ...) -> the rich card
    contract ``events/fragments/comments_card.html`` + ``comment_row.html``
    render: {event, hash, comments, direct_attachments, detail, detail_template, asset_links, header_style, origin_link}.
    """
    from app.events.control_layer.event_context import EventContext
    from app.events.models import EventType
    from app.events.models.details import (
        AdministrationDetail,
        AssetManagementDetail,
        DispatchingDetail,
        InventoryDetail,
        MaintenanceDetail,
    )
    from app.events.presentation_layer.tools.file_previews import build_comments_context
    from app.utils.hashids import encode_id

    ctx = EventContext(thread.pk, user, include_shadow_comments=True)

    detail = None
    detail_template = "events/fragments/details/generic_card.html"

    if thread.event_type == EventType.MAINTENANCE:
        detail_template = "events/fragments/details/maintenance_card.html"
        detail = MaintenanceDetail.objects.filter(pk=thread.pk).select_related(
            "assigned_user", "assigned_by", "completed_by", "meter_reading", "asset"
        ).first()
    elif thread.event_type in (EventType.DISPATCHING, EventType.RESERVATION):
        detail_template = (
            "events/fragments/details/reservation_card.html"
            if thread.event_type == EventType.RESERVATION
            else "events/fragments/details/dispatching_card.html"
        )
        detail = DispatchingDetail.objects.filter(pk=thread.pk).select_related(
            "requested_for", "requested_by", "asset_class"
        ).first()
    elif thread.event_type == EventType.INVENTORY:
        detail_template = "events/fragments/details/inventory_card.html"
        detail = InventoryDetail.objects.filter(pk=thread.pk).first()
    elif thread.event_type == EventType.ASSET_MANAGEMENT:
        detail_template = "events/fragments/details/asset_management_card.html"
        detail = AssetManagementDetail.objects.filter(pk=thread.pk).first()
    elif thread.event_type == EventType.ADMINISTRATION:
        detail_template = "events/fragments/details/administration_card.html"
        detail = AdministrationDetail.objects.filter(pk=thread.pk).first()

    asset_links = list(thread.asset_links.select_related("asset").all())
    header_style = get_event_header_style(thread.event_type)
    origin_link = get_event_origin_link(thread, detail, asset_links)

    unique_assets_dict = {}
    if detail and hasattr(detail, "asset") and detail.asset:
        unique_assets_dict[detail.asset.pk] = detail.asset
    for link in asset_links:
        if link.asset and link.asset.pk not in unique_assets_dict:
            unique_assets_dict[link.asset.pk] = link.asset
    all_associated_assets = list(unique_assets_dict.values())

    direct_attachments = [document_dict(a) for a in ctx.struct.standalone_attachments]
    comment_attachments = []
    for c_struct in ctx.struct.comments:
        for att in c_struct.attachments:
            if att.file.deleted_at is None:
                comment_attachments.append(document_dict(att))

    return {
        "event": thread,
        "hash": encode_id(thread.pk),
        "comments": build_comments_context(ctx.struct),
        "direct_attachments": direct_attachments,
        "comment_attachments": comment_attachments,
        "direct_images": [d for d in direct_attachments if d.get("is_image")],
        "comment_images": [d for d in comment_attachments if d.get("is_image")],
        "detail": detail,
        "detail_template": detail_template,
        "asset_links": asset_links,
        "all_associated_assets": all_associated_assets,
        "header_style": header_style,
        "origin_link": origin_link,
    }
