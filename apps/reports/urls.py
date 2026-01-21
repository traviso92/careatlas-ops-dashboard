"""
Reports URL routes.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.reports_dashboard, name='reports_dashboard'),
    path('compliance/', views.compliance_report, name='compliance_report'),
    path('connectivity/', views.connectivity_report, name='connectivity_report'),
    path('orders/', views.order_pipeline_report, name='order_pipeline_report'),
    # Chart data API endpoints
    path('api/compliance/', views.compliance_chart_data, name='compliance_chart_data'),
    path('api/connectivity/', views.connectivity_chart_data, name='connectivity_chart_data'),
    path('api/orders/', views.order_chart_data, name='order_chart_data'),
]
