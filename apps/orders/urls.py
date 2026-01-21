"""
Order URL patterns.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.order_list, name='order_list'),
    path('create/', views.order_create, name='order_create'),
    path('submit/', views.order_submit, name='order_submit'),
    path('pending/', views.pending_orders, name='pending_orders'),
    path('<str:order_id>/', views.order_detail, name='order_detail'),
    path('<str:order_id>/cancel/', views.order_cancel, name='order_cancel'),
]
