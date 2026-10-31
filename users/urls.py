from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # Root = Home
    path('matchmaking/', views.profile_list, name='profile_list'),
    path('contact/', views.contact_view, name='contact_us'),
    path('contact/verify/', views.contact_verify_view, name='contact_verify'),
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
    path('admin-verify-user/<int:user_id>/', views.admin_verify_user, name='admin_verify_user'),
    path('admin-reject-user/<int:user_id>/', views.admin_reject_user, name='admin_reject_user'),
    path('admin-dismiss-report/<int:report_id>/', views.admin_dismiss_report, name='admin_dismiss_report'),
    path('admin-clear-review/<int:user_id>/', views.admin_clear_review, name='admin_clear_review'),
    path("verify/<str:token>/", views.verify_email, name="verify_email"),
    path(
        "resend-verification/",
        views.resend_verification_email,
        name="resend_verification"
    ),
    path(
        "forgot-password/",
        views.password_reset_request,
        name="password_reset_request"
    ),
    path(
        "forgot-password/verify/",
        views.password_reset_verify,
        name="password_reset_verify"
    ),
    path(
        "forgot-password/confirm/",
        views.password_reset_confirm,
        name="password_reset_confirm"
    ),
]
