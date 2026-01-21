"""URL configuration for CareAtlas Ops Dashboard."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.dashboard.urls')),
    path('patients/', include('apps.patients.urls')),
    path('devices/', include('apps.devices.urls')),
    path('orders/', include('apps.orders.urls')),
    path('vitals/', include('apps.vitals.urls')),
    path('webhooks/', include('apps.webhooks.urls')),
    path('tickets/', include('apps.tickets.urls')),
    path('reports/', include('apps.reports.urls')),
]
