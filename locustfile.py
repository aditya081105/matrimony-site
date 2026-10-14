"""
Load testing suite for Poorvanchal Matrimony using Locust.
Benchmarks throughput, p50/p95 response latencies, and cache hit ratios under simulated concurrent traffic.

Usage:
    locust -f locustfile.py --headless -u 100 -r 20 --run-time 30s --host https://poorvanchalmatrimony.social
"""

from locust import HttpUser, task, between, tag


class MatrimonyVisitorUser(HttpUser):
    """
    Simulates anonymous and browsing visitors on public endpoints,
    evaluating cache-aside performance and database read latency.
    """
    wait_time = between(0.5, 2)

    @tag('public', 'home')
    @task(6)
    def view_home(self):
        self.client.get("/", name="Homepage [GET /]")

    @tag('public', 'plans')
    @task(3)
    def view_plans(self):
        self.client.get("/payments/plans/", name="Membership Plans [GET /payments/plans/]")

    @tag('public', 'info')
    @task(2)
    def view_info_pages(self):
        self.client.get("/about/", name="About Page [GET /about/]")
        self.client.get("/terms/", name="Terms Page [GET /terms/]")
        self.client.get("/privacy/", name="Privacy Page [GET /privacy/]")

    @tag('auth')
    @task(2)
    def view_auth_pages(self):
        self.client.get("/login/", name="Login Page [GET /login/]")
        self.client.get("/forgot-password/", name="Forgot Password [GET /forgot-password/]")

    @tag('search')
    @task(5)
    def search_profiles(self):
        queries = ["engineer", "doctor", "bihar", "patna", "siwan", "teacher", "gorakhpur", "varanasi", "buxar"]
        import random
        q = random.choice(queries)
        self.client.get(f"/search/?q={q}", name="Search Profiles [GET /search/?q=...]")

    @tag('matchmaking')
    @task(3)
    def view_matchmaking_list(self):
        self.client.get("/matchmaking/", name="Matchmaking Feed [GET /matchmaking/]")

