"""
Device URL patterns.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.device_list, name='device_list'),
    path('offline/', views.offline_devices, name='offline_devices'),
    path('<str:device_id>/', views.device_detail, name='device_detail'),
    path('<str:device_id>/status/', views.device_update_status, name='device_update_status'),
    path('<str:device_id>/assign/', views.device_assign, name='device_assign'),
    path('<str:device_id>/return/', views.device_return, name='device_return'),
]
