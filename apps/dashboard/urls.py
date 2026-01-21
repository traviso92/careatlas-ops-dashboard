"""
Dashboard URL patterns.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('stats/', views.dashboard_stats, name='dashboard_stats'),
    path('recent-orders/', views.dashboard_recent_orders, name='dashboard_recent_orders'),
    path('offline-devices/', views.dashboard_offline_devices, name='dashboard_offline_devices'),
    path('offline-devices-count/', views.dashboard_offline_device_count, name='dashboard_offline_device_count'),
    path('search/', views.global_search, name='global_search'),
]
