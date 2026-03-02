from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # Root = Home

    path('matchmaking/', views.profile_list, name='profile_list'),

    path('contact/', views.contact_view, name='contact_us'),

    path('register/', views.register, name='register'),

    path('edit-profile/', views.edit_profile, name='edit_profile'),

    path('my-profile/', views.my_profile, name='my_profile'),
]
