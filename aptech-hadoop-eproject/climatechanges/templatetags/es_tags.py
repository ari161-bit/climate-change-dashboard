from django import template

register = template.Library()


@register.filter
def databadge(label):
    """CSS class for a real/sample data label."""
    label = (label or "").lower()
    if label.startswith("real"):
        return "b-real"
    if label.startswith("sample"):
        return "b-sample"
    if label.startswith("mixed"):
        return "b-mixed"
    return "b-neutral"


@register.filter
def get(d, key):
    try:
        return d.get(key)
    except AttributeError:
        return None


@register.filter
def pct(value, total):
    try:
        return round(100 * float(value) / float(total))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def heat(v):
    """Background colour for a temperature-change table cell."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "transparent"
    if v < 0:
        return "#e0f2fe"
    stops = [(0.25, "#f0fdf4"), (0.5, "#fef9c3"), (0.9, "#fed7aa"), (1.3, "#fdba74"), (99, "#fca5a5")]
    return next(c for t, c in stops if v <= t)
