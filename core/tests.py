from django.test import TestCase, RequestFactory
from django.core.cache import cache
from core.middleware import RequestIDMiddleware
from core.caching import get_active_plans, CACHE_KEY_ACTIVE_PLANS
from payments.models import Plan
from django.http import HttpResponse


class Tier1ArchitectureTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()

    def test_request_id_middleware_injects_header(self):
        request = self.factory.get('/')
        middleware = RequestIDMiddleware(lambda req: HttpResponse("OK"))
        response = middleware(request)

        self.assertIn('X-Request-ID', response.headers)
        self.assertTrue(len(response.headers['X-Request-ID']) > 10)
        self.assertEqual(request.request_id, response.headers['X-Request-ID'])

    def test_cache_aside_active_plans(self):
        # Clear any pre-existing seeded plans for isolated test
        Plan.objects.all().delete()
        cache.clear()

        # Create a test plan
        plan = Plan.objects.create(
            code="test_gold",
            name="Test Gold Plan",
            price=299.00,
            duration_days=30,
            is_active=True
        )

        # First retrieval should be cache miss and populate cache
        self.assertIsNone(cache.get(CACHE_KEY_ACTIVE_PLANS))
        cached_plans = get_active_plans()
        self.assertEqual(len(cached_plans), 1)
        self.assertEqual(cached_plans[0].code, "test_gold")

        # Cache should now be populated
        self.assertIsNotNone(cache.get(CACHE_KEY_ACTIVE_PLANS))

        # Modifying a plan should trigger signal invalidation
        plan.name = "Test Gold Plan Updated"
        plan.save()
        self.assertIsNone(cache.get(CACHE_KEY_ACTIVE_PLANS))
