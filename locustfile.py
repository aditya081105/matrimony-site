"""
Load testing suite for Poorvanchal Matrimony using Locust.
Simulates realistic concurrent traffic patterns across both anonymous visitors
and authenticated members to benchmark throughput, p50/p95 response latencies,
PostgreSQL GIN trigram index performance, and cache hit ratios.

Usage:
    locust -f locustfile.py --headless -u 50 -r 10 --run-time 30s --host https://poorvanchalmatrimony.social
    BENCHMARK_USER=testuser BENCHMARK_PASS=TestPass123! locust -f locustfile.py --host https://poorvanchalmatrimony.social
"""

import os
import random
import re
from locust import HttpUser, task, between, tag


class AnonymousVisitorUser(HttpUser):
    """
    Simulates prospective users and anonymous web crawlers exploring public pages.
    Evaluates Nginx static caching, database read latency, and lightweight public templates.
    """
    weight = 3
    wait_time = between(1, 3)

    @tag('public', 'home')
    @task(5)
    def view_home(self):
        self.client.get("/", name="[Anon] Homepage [GET /]")

    @tag('public', 'plans')
    @task(3)
    def view_plans(self):
        self.client.get("/payments/plans/", name="[Anon] Membership Plans [GET /payments/plans/]")

    @tag('public', 'info')
    @task(2)
    def view_info_pages(self):
        self.client.get("/about/", name="[Anon] About Page [GET /about/]")
        self.client.get("/terms/", name="[Anon] Terms Page [GET /terms/]")
        self.client.get("/privacy/", name="[Anon] Privacy Page [GET /privacy/]")

    @tag('public', 'auth_pages')
    @task(2)
    def view_auth_pages(self):
        self.client.get("/login/", name="[Anon] Login Page [GET /login/]")
        self.client.get("/forgot-password/", name="[Anon] Forgot Password [GET /forgot-password/]")


class AuthenticatedMemberUser(HttpUser):
    """
    Simulates active members navigating search, matchmaking recommendations,
    and profile details. Exercises PostgreSQL GIN trigram indexes and relational joins.
    """
    weight = 7
    wait_time = between(1, 4)

    def on_start(self):
        """Authenticates the simulated member session upon worker start."""
        self.is_logged_in = False
        username = os.getenv("BENCHMARK_USER", "aditya")
        password = os.getenv("BENCHMARK_PASS", "Aditya@12345")

        login_res = self.client.get("/login/", name="[Auth] Fetch Login Form")
        csrf_token = login_res.cookies.get("csrftoken")
        if not csrf_token:
            match = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', login_res.text)
            if match:
                csrf_token = match.group(1)

        if csrf_token:
            post_res = self.client.post(
                "/login/",
                data={
                    "username": username,
                    "password": password,
                    "csrfmiddlewaretoken": csrf_token,
                },
                headers={"Referer": f"{self.host}/login/"},
                name="[Auth] Submit Login Credentials",
                allow_redirects=True,
            )
            if post_res.status_code == 200 and "logout" in post_res.text.lower():
                self.is_logged_in = True

    @tag('search')
    @task(5)
    def search_profiles(self):
        """Tests PostgreSQL Trigram GIN index (pg_trgm) on full_name and occupation."""
        queries = ["engineer", "doctor", "bihar", "patna", "siwan", "teacher", "gorakhpur", "varanasi", "buxar", "software"]
        q = random.choice(queries)
        endpoint_name = "[Auth] Search Profiles [GET /search/?q=...]" if self.is_logged_in else "[Redirect] Search Profiles"
        self.client.get(f"/search/?q={q}", name=endpoint_name)

    @tag('matchmaking')
    @task(4)
    def view_matchmaking_feed(self):
        """Evaluates complex matchmaking query filters and mutual interest checks."""
        endpoint_name = "[Auth] Matchmaking Feed [GET /matchmaking/]" if self.is_logged_in else "[Redirect] Matchmaking Feed"
        self.client.get("/matchmaking/", name=endpoint_name)

    @tag('profiles')
    @task(3)
    def view_profile_detail(self):
        """Views individual profile with privacy authorization checks."""
        profile_id = random.randint(1, 15)
        endpoint_name = f"[Auth] View Profile Detail [GET /profile/{profile_id}/]" if self.is_logged_in else "[Redirect] Profile Detail"
        self.client.get(f"/profile/{profile_id}/", name="[Auth] Profile Detail [GET /profile/:id/]")

    @tag('plans')
    @task(2)
    def view_plans_authenticated(self):
        self.client.get("/payments/plans/", name="[Auth] Membership Plans [GET /payments/plans/]")
