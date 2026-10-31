from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    protocol = 'https'

    def items(self):
        return ['home', 'about', 'contact_us', 'terms', 'privacy', 'register', 'login']

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        priorities = {
            'home': 1.0,
            'register': 0.9,
            'about': 0.8,
            'contact_us': 0.8,
            'login': 0.7,
            'terms': 0.5,
            'privacy': 0.5,
        }
        return priorities.get(item, 0.7)

    def changefreq(self, item):
        if item in ['home', 'register']:
            return 'daily'
        return 'monthly'
