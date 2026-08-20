from django.contrib import admin

from app.events.models import (
    AdministrationDetail,
    AssetManagementDetail,
    Attachment,
    Comment,
    DispatchingDetail,
    Event,
    File,
    GenericDetail,
    InventoryDetail,
    MaintenanceDetail,
    SystemDetail,
)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_type", "status", "priority", "domain", "created_at", "deleted_at")
    list_filter = ("event_type", "status", "priority", "domain")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(MaintenanceDetail)
class MaintenanceDetailAdmin(admin.ModelAdmin):
    list_display = ("title", "maintenance_type", "work_order_reference", "status")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(SystemDetail)
class SystemDetailAdmin(admin.ModelAdmin):
    list_display = ("title", "affected_component", "severity", "status")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(AdministrationDetail)
class AdministrationDetailAdmin(admin.ModelAdmin):
    list_display = ("title", "department", "reference_number", "status")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(AssetManagementDetail)
class AssetManagementDetailAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "domain")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(InventoryDetail)
class InventoryDetailAdmin(admin.ModelAdmin):
    list_display = ("title", "item_category", "location_reference", "status")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(DispatchingDetail)
class DispatchingDetailAdmin(admin.ModelAdmin):
    list_display = ("title", "workflow_status", "requested_for", "dispatch_scope")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(GenericDetail)
class GenericDetailAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "domain")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("pk", "activity_thread", "is_human_made", "revision", "created_by", "deleted_at")
    list_filter = ("is_human_made",)
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by", "origin_id")


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "file_size", "mime_type", "created_by", "deleted_at")
    readonly_fields = ("id", "created_at", "updated_at", "created_by", "updated_by")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "comment", "file", "attachment_type", "display_order")
    readonly_fields = ("id", "created_at", "updated_at", "created_by", "updated_by")
