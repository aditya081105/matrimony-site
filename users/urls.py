from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # Root = Home
    path('matchmaking/', views.profile_list, name='profile_list'),
    path('contact/', views.contact_view, name='contact_us'),
    path('register/', views.register, name='register'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('my-profile/', views.my_profile, name='my_profile'),
    path('terms/', views.terms_view, name='terms'),
    path('privacy/', views.privacy_view, name='privacy'),
    path('about/', views.about_view, name='about'),
    path('matches/', views.my_matches, name='my_matches'),
    path('profile/<int:user_id>/', views.view_profile, name='view_profile'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
]
