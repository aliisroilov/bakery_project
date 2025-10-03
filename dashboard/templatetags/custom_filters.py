from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    """Safely get a value from dictionary."""
    return d.get(key, 0)
