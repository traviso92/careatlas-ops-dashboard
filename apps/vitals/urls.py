"""
Vitals URL patterns.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('patient/<str:patient_id>/', views.patient_vitals, name='patient_vitals'),
    path('patient/<str:patient_id>/chart/', views.vitals_chart_data, name='vitals_chart_data'),
    path('patient/<str:patient_id>/latest/', views.latest_vitals, name='latest_vitals'),
]
