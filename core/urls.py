
from django.urls import path, include # Add 'include' here
from django.contrib import admin
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('secure-admin-panel/', admin.site.urls),
    # PRO WAY: Using Django's built-in auth views
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='users/logout.html'), name='logout'),
    path('profiles/', include('users.urls')), # This connects the users app
    path('', include('users.urls')), # This makes the empty '' go to profiles
    path('interests/', include('communications.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)