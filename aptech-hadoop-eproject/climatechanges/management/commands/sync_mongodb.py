"""Copy all climate data from the SQL database into MongoDB (database `earthscape`)."""
from django.core.management.base import BaseCommand

from climatechanges import mongo


class Command(BaseCommand):
    help = "Sync readings, alerts, jobs, model runs and dataset metadata into MongoDB."

    def handle(self, *args, **opts):
        st = mongo.status()
        if not st["online"]:
            self.stderr.write(self.style.ERROR(st["detail"]))
            return
        result = mongo.sync_all()
        self.stdout.write(self.style.SUCCESS(f"MongoDB {st['version']} synced: {result}"))
