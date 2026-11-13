from django.urls import path

from . import views

app_name = 'climate'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('data/', views.dashboard_data, name='data'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('datasets/', views.explorer, name='explorer'),
    path('datasets/<str:name>/data/', views.explorer_data, name='explorer_data'),
    path('datasets/<str:name>/download/', views.explorer_download, name='explorer_download'),
    path('trends/', views.trends, name='trends'),
    path('trends/options/', views.trends_options, name='trends_options'),
    path('trends/data/', views.trends_data, name='trends_data'),
    path('live/', views.live, name='live'),
    path('live/data/', views.live_data, name='live_data'),
    path('satellite/', views.satellite, name='satellite'),
    path('models/', views.models_page, name='models'),
    path('help/', views.help_page, name='help'),
    path('feedback/', views.feedback, name='feedback'),
    path('manage/', views.admin_panel, name='admin_panel'),
    path('manage/backup/', views.backup_download, name='backup'),
    path('monitor/', views.monitor_page, name='monitor'),
    path('monitor/data/', views.monitor_data, name='monitor_data'),
]
