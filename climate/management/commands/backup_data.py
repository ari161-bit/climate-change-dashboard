import os
import sqlite3
import zipfile
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from climate import lake


class Command(BaseCommand):
    help = 'Write a timestamped backup zip (database snapshot + data lake) to ./backups and keep the newest N.'

    def add_arguments(self, parser):
        parser.add_argument('--keep', type=int, default=7)
        parser.add_argument('--dir', default=os.path.join(settings.BASE_DIR, 'backups'))

    def handle(self, *args, **options):
        os.makedirs(options['dir'], exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        target = os.path.join(options['dir'], f'earthscape-backup-{stamp}.zip')
        snapshot = target + '.db'
        source, dest = sqlite3.connect(str(connection.settings_dict['NAME'])), sqlite3.connect(snapshot)
        with dest:
            source.backup(dest)
        source.close()
        dest.close()
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, 'database.sqlite3')
            for root, _, files in os.walk(lake.LAKE_DIR):
                for fname in files:
                    full = os.path.join(root, fname)
                    archive.write(full, os.path.join('lake', os.path.relpath(full, lake.LAKE_DIR)))
        os.unlink(snapshot)
        old = sorted(f for f in os.listdir(options['dir']) if f.startswith('earthscape-backup-') and f.endswith('.zip'))[:-options['keep']]
        for name in old:
            os.unlink(os.path.join(options['dir'], name))
        self.stdout.write(self.style.SUCCESS(f'Backup written to {target} ({os.path.getsize(target) // 1024} KB); removed {len(old)} old.'))
