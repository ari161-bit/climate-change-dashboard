from django.utils import timezone


def maintenance(request):
    """Upcoming / ongoing scheduled maintenance, shown as a banner on every page."""
    try:
        from .models import MaintenanceNotice
        now = timezone.now()
        notices = list(MaintenanceNotice.objects.filter(active=True, ends_at__gte=now)
                       .filter(starts_at__lte=now + timezone.timedelta(days=14))[:3])
    except Exception:
        notices = []
    return {"maintenance_notices": notices}
