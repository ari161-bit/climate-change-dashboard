from django.urls import path

from . import views, console_views as cv
from django.conf.urls.static import static

urlpatterns = [

    path("", views.index, name="index"),

    path('index/', views.index, name='index'),

     path('about/', views.about, name='about'),

    path("signup/", views.signup, name="signup"),

    path("login/", views.login_view, name="login"),

    path("logout/", views.logout_view, name="logout"),

    path("dataset/", views.dataset, name="dataset"),

    path("support/", views.support, name="support"),

    path("profile/", views.profile, name="profile"),


    # ---- EarthScape console ----
    path("console/", cv.overview, name="console_overview"),
    path("console/analytics/", cv.analytics, name="console_analytics"),
    path("console/data/", cv.data_management, name="console_data"),
    path("console/data/<int:pk>/", cv.dataset_detail, name="console_dataset"),
    path("console/data/<int:pk>/download/<str:which>/", cv.dataset_download, name="console_dataset_download"),
    path("console/processing/", cv.processing, name="console_processing"),
    path("console/processing/job/<int:pk>/", cv.job_detail, name="console_job"),
    path("console/predictions/", cv.predictions, name="console_predictions"),
    path("console/anomalies/", cv.anomalies, name="console_anomalies"),
    path("console/alerts/", cv.alerts_view, name="console_alerts"),
    path("console/reports/", cv.reports_view, name="console_reports"),
    path("console/support/", cv.support_view, name="console_support"),
    path("console/support/<int:pk>/", cv.support_detail, name="console_support_detail"),
    path("console/settings/", cv.settings_view, name="console_settings"),
    path("console/users/", cv.users_view, name="console_users"),
    path("console/help/", cv.help_view, name="console_help"),
    # ---- REST API ----
    path("api/summary/", cv.api_summary, name="api_summary"),
    path("api/alerts/unread/", cv.api_alerts_unread, name="api_alerts_unread"),
    path("api/series/", cv.api_series, name="api_series"),
    path("api/ingest/", cv.api_ingest, name="api_ingest"),
    path("api/health/", cv.api_health, name="api_health"),
    path("api/chat/", views.chat_api, name="api_chat"),

    path("<slug:name>.html", views.page, name="page"),


]