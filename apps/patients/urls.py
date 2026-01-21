"""
Patient URL patterns.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.patient_list, name='patient_list'),
    path('create/', views.patient_create, name='patient_create'),
    path('search/', views.patient_search_api, name='patient_search_api'),
    path('<str:patient_id>/', views.patient_detail, name='patient_detail'),
    path('<str:patient_id>/edit/', views.patient_edit, name='patient_edit'),
]
