from django.conf import settings
from django.db import models


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
    message = models.TextField(max_length=2000)
    status = models.CharField(max_length=10, choices=STATUSES, default='open')
    response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'feedback'

    def __str__(self):
        return f'{self.subject} ({self.status})'
