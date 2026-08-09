from django import template

register = template.Library()

@register.filter(name='split')
def split(value, arg):
    """Returns the string split by arg"""
    if value:
        return value.split(arg)
    return []

@register.filter(name='mul')
def mul(value, arg):
    """Multiplies value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
