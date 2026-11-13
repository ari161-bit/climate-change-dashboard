import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AlertThreshold',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=40, unique=True)),
                ('label', models.CharField(max_length=80)),
                ('value', models.FloatField()),
                ('unit', models.CharField(blank=True, max_length=20)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['id']},
        ),
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('question', 'Question'), ('bug', 'Report a problem'), ('data', 'Data / methodology'), ('suggestion', 'Suggestion')], default='question', max_length=20)),
                ('subject', models.CharField(max_length=120)),
                ('message', models.TextField(max_length=2000)),
                ('status', models.CharField(choices=[('open', 'Open'), ('resolved', 'Resolved')], default='open', max_length=10)),
                ('response', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='climate_feedback', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name_plural': 'feedback', 'ordering': ['-created_at']},
        ),
    ]
