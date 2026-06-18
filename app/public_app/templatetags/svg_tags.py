from django import template
from django.contrib.staticfiles import finders
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def svg(name):
    path = finders.find(f"icons/{name}.svg")
    if not path:
        return ""
    with open(path) as f:
        return mark_safe(f.read())
