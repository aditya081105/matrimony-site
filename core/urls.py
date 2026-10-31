from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse

from django.conf import settings
from django.conf.urls.static import static

from users.forms import RateLimitedAuthenticationForm
from .sitemaps import StaticViewSitemap

sitemaps = {
    'static': StaticViewSitemap,
}


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin-dashboard/",
        "Disallow: /secure-admin-panel/",
        "Disallow: /admin-verify-user/",
        "Disallow: /admin-reject-user/",
        "Disallow: /admin-unsuspend-user/",
        "Disallow: /admin-dismiss-report/",
        "Disallow: /admin-clear-review/",
        "Disallow: /delete-account/",
        "Disallow: /edit-profile/",
        "Disallow: /my-profile/",
        "Disallow: /matches/",
        "Disallow: /matchmaking/",
        "Disallow: /interests/",
        "Disallow: /payments/",
        "Disallow: /verify/",
        "Disallow: /resend-verification/",
        "Disallow: /forgot-password/",
        "Disallow: /contact/verify/",
        "",
        "Sitemap: https://poorvanchalmatrimony.social/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    path('secure-admin-panel/', admin.site.urls),

    path('login/', auth_views.LoginView.as_view(
        template_name='users/login.html',
        authentication_form=RateLimitedAuthenticationForm
    ), name='login'),

    path('logout/', auth_views.LogoutView.as_view(
        template_name='users/logout.html'
    ), name='logout'),

    path('profiles/', include('users.urls')),
    path('', include('users.urls')),
    path('interests/', include('communications.urls')),
    path('payments/', include('payments.urls')),
    path('search/', include('search.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
