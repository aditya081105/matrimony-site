from django.urls import path
from . import views

urlpatterns = [
    path('send/<int:user_id>/', views.send_request, name='send_request'),
    path('received/', views.received_requests, name='received_requests'),
    path('update/<int:request_id>/<str:action>/', views.update_request, name='update_request'),
    path('unmatch/<int:user_id>/', views.unmatch, name='unmatch'),
    path('cancel/<int:user_id>/', views.cancel_request, name='cancel_request'),
    path('block/<int:user_id>/', views.block_user, name='block_user'),
    path('report/<int:user_id>/', views.report_user, name='report_user'),
    path('blocked/', views.blocked_users, name='blocked_users'),
    path('unblock/<int:user_id>/', views.unblock_user, name='unblock_user'),
    path("save/<int:user_id>/", views.toggle_save, name="toggle_save"),
    path("saved/", views.saved_profiles, name="saved_profiles"),
]