from django.urls import path

from . import views, dashboard_views
from django.conf.urls.static import static

urlpatterns = [
      
    path("", views.index, name="index"),

    path('index/', views.index, name='index'),

    path('about/', views.about, name='about'),

    path('contact/', views.contact, name='contact'),

    path('shop/', views.shop, name='shop'),

    path('shopdetail/<int:id>', views.shopdetail, name='shopdetail'),

    path('cart/', views.cart, name='cart'),

    path('add_to_cart/<int:id>/', views.add_to_cart, name='add_to_cart'),

    path('remove_from_cart/<int:id>/', views.remove_from_cart, name='remove_from_cart'),

    path('checkout/', views.checkout, name='checkout'),

    path('signup/', views.signup, name='signup'),

    path('login/', views.login_view, name='login'),

    path('realestatesearch/', views.realEstateSearch, name='realestatesearch'),

    path('realEstateGraph/', views.realEstateGraph, name='realEstateGraph'),

    path('JQUERYGraph/', views.JQUERYGraph, name='JQUERYGraph'),

    path('realEstateGraphbycity/', views.realEstateGraphbycity, name='realEstateGraphbycity'),

    path('realEstatePrediction/', views.realEstatePrediction, name='realEstatePrediction'),

    path('realEstatePrediction2/', views.realEstatePrediction2, name='realEstatePrediction2'),

    path('realEstateDashboard/', dashboard_views.realEstateDashboard, name='realEstateDashboard'),

    path('realEstateDashboardData/', dashboard_views.realEstateDashboardData, name='realEstateDashboardData'),
] 
