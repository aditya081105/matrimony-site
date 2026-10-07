from django.test import TestCase
from django.urls import reverse
from users.models import CustomUser, Subscription
from payments.models import Plan, PaymentOrder


class PaymentTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="buyer1",
            email="buyer1@test.com",
            password="TestPassword123!",
            full_name="Buyer One",
            gender="M",
            phone_number="9876543210",
        )
        self.client.login(username="buyer1", password="TestPassword123!")

    def test_plans_page_loads_and_seeds(self):
        response = self.client.get(reverse('plans'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Plan.objects.count() >= 3)
        self.assertContains(response, "Gold Plan")

    def test_checkout_page_loads(self):
        self.client.get(reverse('plans'))  # ensures seeding
        response = self.client.get(reverse('checkout', args=['gold']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Scan & Pay")

    def test_submit_utr_creates_order(self):
        self.client.get(reverse('plans'))
        response = self.client.post(
            reverse('checkout', args=['gold']),
            {'action': 'submit_utr', 'utr_number': '123456789012'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        order = PaymentOrder.objects.filter(user=self.user, utr_number='123456789012').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, 'pending')

    def test_order_activation_updates_subscription(self):
        self.client.get(reverse('plans'))
        plan = Plan.objects.get(code='gold')
        order = PaymentOrder.objects.create(
            user=self.user,
            plan=plan,
            amount=plan.price,
            utr_number="TEST_UTR_1234",
            status="pending",
        )

        self.assertFalse(self.user.is_premium)
        order.activate_subscription()

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_premium)
        self.assertTrue(self.user.subscription.is_active)
        self.assertEqual(self.user.subscription.plan_type, plan.name)
