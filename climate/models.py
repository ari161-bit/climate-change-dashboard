from django.conf import settings
from django.db import models

from . import crypto


class AlertThreshold(models.Model):
    key = models.CharField(max_length=40, unique=True)
    label = models.CharField(max_length=80)
    value = models.FloatField()
    unit = models.CharField(max_length=20, blank=True)
    description = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.label}: {self.value} {self.unit}'


class Feedback(models.Model):
    """Support request. The message and the reply are encrypted at rest."""
    CATEGORIES = [
        ('question', 'Question'),
        ('bug', 'Report a problem'),
        ('data', 'Data / methodology'),
        ('suggestion', 'Suggestion'),
    ]
    STATUSES = [('open', 'Open'), ('resolved', 'Resolved')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='climate_feedback')
    category = models.CharField(max_length=20, choices=CATEGORIES, default='question')
    subject = models.CharField(max_length=120)
    message_enc = models.TextField()
    status = models.CharField(max_length=10, choices=STATUSES, default='open')
    response_enc = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'feedback'

    @property
    def message(self):
        return crypto.decrypt(self.message_enc)

    @message.setter
    def message(self, value):
        self.message_enc = crypto.encrypt(value)

    @property
    def response(self):
        return crypto.decrypt(self.response_enc)

    @response.setter
    def response(self, value):
        self.response_enc = crypto.encrypt(value)

    def __str__(self):
        return f'{self.subject} ({self.status})'


class ModelRun(models.Model):
    """One (re)training of an analytics model, kept so quality can be tracked over time."""
    name = models.CharField(max_length=60)
    trained_at = models.DateTimeField(auto_now_add=True)
    data_through = models.CharField(max_length=20)
    params = models.JSONField(default=dict)
    metrics = models.JSONField(default=dict)
    duration_ms = models.FloatField(default=0)
    triggered_by = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ['-trained_at']

    def __str__(self):
        return f'{self.name} @ {self.trained_at:%Y-%m-%d %H:%M}'


class AuditLog(models.Model):
    """Who did what: sign-ins, uploads, retraining, threshold changes."""
    at = models.DateTimeField(auto_now_add=True)
    user = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=60)
    detail = models.CharField(max_length=300, blank=True)
    ip = models.CharField(max_length=45, blank=True)

    class Meta:
        ordering = ['-at']

    def __str__(self):
        return f'{self.at:%Y-%m-%d %H:%M} {self.user} {self.action}'


class CustomDataset(models.Model):
    """A dataset uploaded by an administrator (CSV/JSON/XLS with a year-or-date column and one value column)."""
    VISIBILITY = [('analysts', 'Administrators and analysts'), ('admins', 'Administrators only')]

    slug = models.SlugField(max_length=60, unique=True)
    title = models.CharField(max_length=120)
    unit = models.CharField(max_length=30, blank=True)
    source = models.CharField(max_length=200, blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY, default='analysts')
    points = models.JSONField(default=list)  # [[year, value], ...]
    uploaded_by = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
