"""One command to prepare a fresh install: roles, alert rules, sample data, models, alerts."""
from django.core.management import call_command
from django.core.management.base import BaseCommand

from climatechanges import alerts, roles
from climatechanges.mapreduce import run_job


class Command(BaseCommand):
    help = "Create roles + default alert rules, seed sample readings, train models and evaluate alerts."

    def add_arguments(self, parser):
        parser.add_argument("--no-sample", action="store_true", help="skip generating sample readings")

    def handle(self, *args, **opts):
        roles.ensure_groups()
        self.stdout.write(f"Roles ready: {roles.ADMIN}, {roles.ANALYST}")
        n = alerts.seed_default_rules()
        self.stdout.write(f"Default alert rules created: {n}")
        if not opts["no_sample"]:
            call_command("seed_sample_data")
        for job in ("yearly_temperature", "disasters_per_year", "regional_averages", "train_models",
                    "anomaly_scan", "evaluate_alerts"):
            j = run_job(job)
            self.stdout.write(f"  {job}: {j.status} ({j.duration_ms} ms){' - ' + j.error if j.error else ''}")
        self.stdout.write(self.style.SUCCESS("EarthScape is ready."))
