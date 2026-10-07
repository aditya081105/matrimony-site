from django.urls import path
from . import views

urlpatterns = [
    path('plans/', views.plans_view, name='plans'),
    path('checkout/<str:plan_code>/', views.checkout_view, name='checkout'),
    path('history/', views.payment_history_view, name='payment_history'),
    path('activate-demo/<int:order_id>/', views.simulate_instant_activation, name='simulate_instant_activation'),
]
