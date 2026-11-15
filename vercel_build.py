"""Collect static assets for the nested Aptech eProject Django app on Vercel."""
import os
import sys
from pathlib import Path

project = Path(__file__).resolve().parent / "aptech-hadoop-eproject"
sys.path.insert(0, str(project))
os.environ.setdefault("VERCEL", "1")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django
from django.core.management import call_command

django.setup()
call_command("collectstatic", interactive=False, verbosity=1)
