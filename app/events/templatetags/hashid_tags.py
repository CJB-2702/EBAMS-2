from django import template
from app.utils.hashids import encode_id as _encode_id

register = template.Library()


@register.filter
def encode_id(pk):
    """Encode an integer PK to a hashid string. Usage: {{ event.pk|encode_id }}"""
    if pk is None:
        return ""
    return _encode_id(int(pk))


@register.filter
def has_images(att_list):
    """Check if the attachment list contains any image files."""
    if not att_list:
        return False
    for item in att_list:
        try:
            # item is a dict with "attachment" key in comments_context
            attachment = item.get("attachment")
            if attachment and attachment.file.is_image():
                return True
        except (AttributeError, TypeError):
            pass
    return False

