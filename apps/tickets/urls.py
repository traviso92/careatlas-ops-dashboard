"""
Ticket URL routes.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.ticket_list, name='ticket_list'),
    path('create/', views.ticket_create, name='ticket_create'),
    path('<str:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('<str:ticket_id>/message/', views.ticket_add_message, name='ticket_add_message'),
    path('<str:ticket_id>/status/', views.ticket_update_status, name='ticket_update_status'),
]
