from django.urls import path

from . import views

app_name = 'climate'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('data/', views.dashboard_data, name='data'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('feedback/', views.feedback, name='feedback'),
    path('manage/', views.admin_panel, name='admin_panel'),
]
