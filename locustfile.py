"""
Load testing suite for Siwan Matrimony using Locust.
Benchmarks throughput, p50/p95 response latencies, and cache hit ratios under simulated concurrent traffic.

Usage:
    locust -f locustfile.py --headless -u 50 -r 10 --run-time 1m --host http://127.0.0.1:8000
"""

from locust import HttpUser, task, between, tag


class MatrimonyVisitorUser(HttpUser):
    """
    Simulates anonymous and browsing visitors on public endpoints,
    evaluating cache-aside performance and database read latency.
    """
    wait_time = between(1, 3)

    @tag('public', 'home')
    @task(5)
    def view_home(self):
        self.client.get("/", name="Homepage [GET /]")

    @tag('public', 'plans')
    @task(3)
    def view_plans(self):
        self.client.get("/payments/plans/", name="Membership Plans [GET /payments/plans/]")

    @tag('public', 'info')
    @task(1)
    def view_info_pages(self):
        self.client.get("/about/", name="About Page [GET /about/]")
        self.client.get("/terms/", name="Terms Page [GET /terms/]")
        self.client.get("/privacy/", name="Privacy Page [GET /privacy/]")

    @tag('search')
    @task(4)
    def search_profiles(self):
        queries = ["engineer", "doctor", "bihar", "patna", "siwan", "teacher"]
        import random
        q = random.choice(queries)
        self.client.get(f"/search/?q={q}", name="Search Profiles [GET /search/?q=...]")

    @tag('matchmaking')
    @task(3)
    def view_matchmaking_list(self):
        # Unauthenticated request redirects to login or loads matchmaking
        self.client.get("/matchmaking/", name="Matchmaking Feed [GET /matchmaking/]")
