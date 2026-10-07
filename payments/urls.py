from django.urls import path
from . import views

urlpatterns = [
    path('plans/', views.plans_view, name='plans'),
    path('checkout/<str:plan_code>/', views.checkout_view, name='checkout'),
    path('history/', views.payment_history_view, name='payment_history'),
]
