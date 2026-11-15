"""Restore a backup made by backup_earthscape.

    python manage.py restore_earthscape backups/earthscape_20261104_180000.zip.enc

Stop the web server first. The current database is kept as db.sqlite3.before_restore.
"""
import io
import shutil
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from climatechanges import crypto


class Command(BaseCommand):
    help = "Decrypt and restore an EarthScape backup (database, uploads, data)."

    def add_arguments(self, parser):
        parser.add_argument("backup", help="path to earthscape_<timestamp>.zip.enc")

    def handle(self, *args, **opts):
        path = Path(opts["backup"])
        if not path.exists():
            raise CommandError(f"{path} not found")
        try:
            data = crypto.decrypt(path.read_bytes())
        except ValueError as e:
            raise CommandError(str(e))
        base = Path(settings.BASE_DIR)
        db = Path(settings.DATABASES["default"]["NAME"])
        if db.exists():
            shutil.copyfile(db, db.with_name(db.name + ".before_restore"))
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                target = (base / name).resolve()
                if base.resolve() not in target.parents and target != base.resolve() / db.name:
                    raise CommandError(f"unsafe path in backup: {name}")
            z.extractall(base)
        self.stdout.write(self.style.SUCCESS(f"Restored {path.name}. Previous database saved as {db.name}.before_restore"))
