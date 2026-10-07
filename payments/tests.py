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

    def test_duplicate_utr_rejected(self):
        self.client.get(reverse('plans'))
        self.client.post(
            reverse('checkout', args=['gold']),
            {'action': 'submit_utr', 'utr_number': '987654321098'},
            follow=True
        )
        # Attempt duplicate
        self.client.post(
            reverse('checkout', args=['gold']),
            {'action': 'submit_utr', 'utr_number': '987654321098'},
            follow=True
        )
        self.assertEqual(PaymentOrder.objects.filter(utr_number='987654321098').count(), 1)

    def test_invalid_utr_format_rejected(self):
        self.client.get(reverse('plans'))
        # Too short (not 12 chars)
        self.client.post(
            reverse('checkout', args=['gold']),
            {'action': 'submit_utr', 'utr_number': '12345'},
            follow=True
        )
        self.assertEqual(PaymentOrder.objects.filter(utr_number='12345').count(), 0)

        # Special characters
        self.client.post(
            reverse('checkout', args=['gold']),
            {'action': 'submit_utr', 'utr_number': '1234567890@#'},
            follow=True
        )
        self.assertEqual(PaymentOrder.objects.filter(utr_number='1234567890@#').count(), 0)

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

    def test_supersede_previous_completed_orders(self):
        self.client.get(reverse('plans'))
        silver_plan = Plan.objects.get(code='silver')
        gold_plan = Plan.objects.get(code='gold')

        order1 = PaymentOrder.objects.create(
            user=self.user,
            plan=silver_plan,
            amount=silver_plan.price,
            utr_number="UTR_ORDER_1",
            status="pending",
        )
        order1.activate_subscription()
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription.plan_type, silver_plan.name)
        self.assertEqual(order1.status, 'completed')

        # Activate gold plan
        order2 = PaymentOrder.objects.create(
            user=self.user,
            plan=gold_plan,
            amount=gold_plan.price,
            utr_number="UTR_ORDER_2",
            status="pending",
        )
        order2.activate_subscription()

        order1.refresh_from_db()
        order2.refresh_from_db()
        self.user.refresh_from_db()

        # Previous order superseded, current active
        self.assertEqual(order1.status, 'superseded')
        self.assertEqual(order2.status, 'completed')
        self.assertEqual(self.user.subscription.plan_type, gold_plan.name)
        self.assertEqual(self.user.subscription.active_order, order2)

    def test_plan_deletion_resets_user_subscription(self):
        self.client.get(reverse('plans'))
        silver_plan = Plan.objects.get(code='silver')
        order = PaymentOrder.objects.create(
            user=self.user,
            plan=silver_plan,
            amount=silver_plan.price,
            utr_number="UTR_SILVER",
            status="pending",
        )
        order.activate_subscription()
        self.user.refresh_from_db()
        self.assertTrue(self.user.subscription.is_active)

        # Delete the order and plan
        order.delete()
        self.user.refresh_from_db()
        self.assertFalse(self.user.subscription.is_active)
        self.assertEqual(self.user.subscription.plan_type, 'Free')
