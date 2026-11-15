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

def application(environ, start_response):
    """Initialize the ephemeral demo database once per serverless instance."""
    global _bootstrapped
    if not _bootstrapped:
        from django.core.management import call_command
        from climatechanges import alerts, roles
        call_command("migrate", interactive=False, verbosity=0)
        roles.ensure_groups()
        alerts.seed_default_rules()
        _bootstrapped = True
    return django_app(environ, start_response)

app = application

app = application
