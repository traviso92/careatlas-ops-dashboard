"""
Webhook URL patterns.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('tenovi/measurement/', views.measurement_webhook, name='webhook_measurement'),
    path('tenovi/fulfillment/', views.fulfillment_webhook, name='webhook_fulfillment'),
    path('tenovi/device-registration/', views.device_registration_webhook, name='webhook_device_registration'),
    path('status/', views.webhook_status, name='webhook_status'),
]
