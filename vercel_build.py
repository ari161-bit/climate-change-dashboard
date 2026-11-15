"""Collect static assets for the nested Aptech eProject Django app on Vercel."""
import os
import shutil
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

# The linked Vercel project expects its static output in `public`. Mirror
# Django's collected files under /static so template URLs resolve from the CDN.
from django.conf import settings

repo_root = Path(__file__).resolve().parent
public_root = repo_root / "public"
if public_root.exists():
    shutil.rmtree(public_root)
public_static = public_root / "static"
public_static.mkdir(parents=True)
shutil.copytree(settings.STATIC_ROOT, public_static, dirs_exist_ok=True)
