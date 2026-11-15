from django.contrib import admin
from .models import Customer, Feedback
# Register your models here.

admin.site.register(Customer)

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "email", "created", "resolved")
    list_filter = ("kind", "resolved")
