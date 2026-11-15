"""Vercel entrypoint for the required Aptech Hadoop eProject."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent / "aptech-hadoop-eproject"
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

from django.core.wsgi import get_wsgi_application

django_app = get_wsgi_application()
_bootstrapped = False

DEMO_USERS = [
    ("admin_demo", "Climate#Admin2026", "ADMIN", True),
    ("analyst_demo", "Climate#Analyst2026", "ANALYST", False),
]


def _create_demo_users(roles):
    """Recreate the README demo accounts in the fresh serverless database."""
    from django.contrib.auth.models import Group, User
    for username, password, role, staff in DEMO_USERS:
        user, _ = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.is_staff = user.is_superuser = staff
        user.save()
        user.groups.add(Group.objects.get_or_create(name=getattr(roles, role))[0])

def application(environ, start_response):
    """Initialize the ephemeral demo database once per serverless instance."""
    global _bootstrapped
    if not _bootstrapped:
        from django.core.management import call_command
        from climatechanges import alerts, roles
        call_command("migrate", interactive=False, verbosity=0)
        roles.ensure_groups()
        alerts.seed_default_rules()
        _create_demo_users(roles)
        try:
            call_command("seed_sample_data", verbosity=0)
        except Exception:
            pass
        _bootstrapped = True
    return django_app(environ, start_response)

app = application
