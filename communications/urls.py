from django.urls import path
from . import views

urlpatterns = [
    path('send/<int:user_id>/', views.send_request, name='send_request'),
]