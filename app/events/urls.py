from django.urls import path

from app.events.presentation_layer.entrypoints.events import (
    event_create,
    event_detail,
    event_edit,
    event_index,
    event_soft_delete,
)
from app.events.presentation_layer.entrypoints.comments import (
    comment_add,
    comment_edit,
    comment_history,
    comment_soft_delete,
)
from app.events.presentation_layer.entrypoints.files import (
    file_download,
    file_inline,
    file_soft_delete,
    file_upload,
)

urlpatterns = [
    # Events
    path("", event_index, name="event_index"),
    path("create/", event_create, name="event_create"),
    path("<str:hash>/", event_detail, name="event_detail"),
    path("<str:hash>/edit/", event_edit, name="event_edit"),
    path("<str:hash>/delete/", event_soft_delete, name="event_soft_delete"),

    # Comments (scoped to an event)
    path("<str:event_hash>/comments/add/", comment_add, name="comment_add"),
    path("<str:event_hash>/comments/<str:comment_hash>/edit/", comment_edit, name="comment_edit"),
    path("<str:event_hash>/comments/<str:comment_hash>/history/", comment_history, name="comment_history"),
    path("<str:event_hash>/comments/<str:comment_hash>/delete/", comment_soft_delete, name="comment_soft_delete"),

    # Files
    path("<str:event_hash>/files/upload/", file_upload, name="file_upload"),
    path("files/<uuid:file_id>/download/", file_download, name="file_download"),
    path("files/<uuid:file_id>/inline/", file_inline, name="file_inline"),
    path("files/<uuid:file_id>/delete/", file_soft_delete, name="file_soft_delete"),
]
