from django.db import migrations, models


def encrypt_existing(apps, schema_editor):
    from climate import crypto
    Feedback = apps.get_model('climate', 'Feedback')
    for item in Feedback.objects.all():
        item.message_enc = crypto.encrypt(item.message_enc)
        item.response_enc = crypto.encrypt(item.response_enc)
        item.save(update_fields=['message_enc', 'response_enc'])


class Migration(migrations.Migration):

    dependencies = [('climate', '0001_initial')]

    operations = [
        migrations.RenameField('feedback', 'message', 'message_enc'),
        migrations.RenameField('feedback', 'response', 'response_enc'),
        migrations.AlterField('feedback', 'message_enc', models.TextField()),
        migrations.RunPython(encrypt_existing, migrations.RunPython.noop),
        migrations.CreateModel(
            name='ModelRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=60)),
                ('trained_at', models.DateTimeField(auto_now_add=True)),
                ('data_through', models.CharField(max_length=20)),
                ('params', models.JSONField(default=dict)),
                ('metrics', models.JSONField(default=dict)),
                ('duration_ms', models.FloatField(default=0)),
                ('triggered_by', models.CharField(blank=True, max_length=60)),
            ],
            options={'ordering': ['-trained_at']},
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('at', models.DateTimeField(auto_now_add=True)),
                ('user', models.CharField(blank=True, max_length=150)),
                ('action', models.CharField(max_length=60)),
                ('detail', models.CharField(blank=True, max_length=300)),
                ('ip', models.CharField(blank=True, max_length=45)),
            ],
            options={'ordering': ['-at']},
        ),
        migrations.CreateModel(
            name='CustomDataset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=60, unique=True)),
                ('title', models.CharField(max_length=120)),
                ('unit', models.CharField(blank=True, max_length=30)),
                ('source', models.CharField(blank=True, max_length=200)),
                ('visibility', models.CharField(choices=[('analysts', 'Administrators and analysts'), ('admins', 'Administrators only')], default='analysts', max_length=10)),
                ('points', models.JSONField(default=list)),
                ('uploaded_by', models.CharField(blank=True, max_length=150)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
