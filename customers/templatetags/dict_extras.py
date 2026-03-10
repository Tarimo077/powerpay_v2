from django import template
register = template.Library()

@register.filter
def get_item(d, key):
    return d.get(key)

@register.filter(name="add_class")
def add_class(field, css):
    return field.as_widget(attrs={"class": css})

@register.filter(name='abs')
def abs_filter(value):
    try:
        return abs(value)
    except (TypeError, ValueError):
        return value