"""Backup procedure: database + uploaded files + data folder -> backups/earthscape_<timestamp>.zip.enc

The zip is encrypted with the data key (climatechanges/crypto.py).
Restore:   python manage.py restore_earthscape backups/earthscape_<timestamp>.zip.enc
Automate:  deploy/schedule_backup.cmd registers a daily Windows Scheduled Task.
"""
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


def make_backup(keep=14):
    base = Path(settings.BASE_DIR)
    out_dir = Path(settings.BACKUP_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    import io
    from climatechanges import crypto
    target = out_dir / f"earthscape_{datetime.now():%Y%m%d_%H%M%S}.zip.enc"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        db = Path(settings.DATABASES["default"]["NAME"])
        if db.exists():
            z.write(db, db.name)
        for folder in (Path(settings.MEDIA_ROOT), Path(settings.DATA_DIR)):
            if folder.exists():
                for f in folder.rglob("*"):
                    if f.is_file() and "hdfs_staging" not in f.parts:
                        z.write(f, f.relative_to(base))
    target.write_bytes(crypto.encrypt(buf.getvalue()))
    backups = sorted(out_dir.glob("earthscape_*.zip*"))
    for old in backups[:-keep]:
        old.unlink()
    return target


class Command(BaseCommand):
    help = "Create a zip backup of the database, uploads and data."

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=14, help="how many backups to keep")

    def handle(self, *args, **opts):
        path = make_backup(opts["keep"])
        self.stdout.write(self.style.SUCCESS(f"Backup written to {path}"))
