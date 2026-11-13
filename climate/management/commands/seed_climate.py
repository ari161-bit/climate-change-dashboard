from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from climate.analytics import DEFAULT_THRESHOLDS
from climate.models import AlertThreshold

DEMO_USERS = [
    ('admin_demo', 'Climate#Admin2026', 'Administrators'),
    ('analyst_demo', 'Climate#Analyst2026', 'Analysts'),
]


class Command(BaseCommand):
    help = 'Create the Administrators/Analysts groups, default alert thresholds and demo accounts.'

    def handle(self, *args, **options):
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in ('Administrators', 'Analysts')}
        for key, label, value, unit, desc in DEFAULT_THRESHOLDS:
            AlertThreshold.objects.get_or_create(key=key, defaults={
                'label': label, 'value': value, 'unit': unit, 'description': desc})
        for username, password, group in DEMO_USERS:
            user, created = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.is_staff = False
            user.is_superuser = False
            user.save()
            user.groups.set([groups[group]])
            self.stdout.write(f'{"created" if created else "updated"} {username} ({group})')
        self.stdout.write(self.style.SUCCESS('Seed complete.'))
