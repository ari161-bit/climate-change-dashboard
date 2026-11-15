"""Role-based access control: Administrator and Climate Analyst."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

ADMIN = "Administrator"
ANALYST = "Climate Analyst"
LEGACY_ANALYST = "Analyst"   # name used by earlier versions of the signup view


def ensure_groups():
    Group.objects.get_or_create(name=ADMIN)
    Group.objects.get_or_create(name=ANALYST)


def is_admin(user):
    return bool(user and user.is_authenticated and
                (user.is_superuser or user.is_staff or user.groups.filter(name=ADMIN).exists()))


def role_of(user):
    if not (user and user.is_authenticated):
        return None
    return ADMIN if is_admin(user) else ANALYST


def assign_role(user, role):
    """Give a user exactly one EarthScape role."""
    ensure_groups()
    user.groups.remove(*Group.objects.filter(name__in=[ADMIN, ANALYST, LEGACY_ANALYST]))
    user.groups.add(Group.objects.get(name=role))
    user.is_staff = role == ADMIN   # admins can also use the Django admin site
    user.save(update_fields=["is_staff"])


def admin_required(view):
    """Logged in AND Administrator, otherwise 403."""
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied("Administrator role required.")
        return view(request, *args, **kwargs)
    return wrapper


def api_login_required(view):
    """For JSON endpoints: 401 JSON instead of a login redirect."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "authentication required"}, status=401)
        return view(request, *args, **kwargs)
    return wrapper
