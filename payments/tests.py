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
            is_approved=True,
            is_email_verified=True,
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

    def test_unapproved_user_blocked_from_checkout(self):
        self.user.is_approved = False
        self.user.save()
        response = self.client.get(reverse('checkout', args=['gold']))
        self.assertContains(response, "Pending Approval")

    def test_unverified_user_blocked_from_checkout(self):
        self.user.is_email_verified = False
        self.user.save()
        response = self.client.get(reverse('checkout', args=['gold']))
        self.assertContains(response, "Verify Your Email")

    def test_suspended_user_blocked_from_checkout(self):
        self.user.is_suspended = True
        self.user.save()
        response = self.client.get(reverse('checkout', args=['gold']))
        self.assertEqual(response.status_code, 302)


class PaymentStateMachineTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="state_user",
            email="state_user@test.com",
            password="TestPassword123!",
            full_name="State User",
            gender="M",
            phone_number="9876543211",
            is_approved=True,
            is_email_verified=True,
        )
        self.silver, _ = Plan.objects.get_or_create(
            code="silver",
            defaults={"name": "Silver Plan", "price": 999.00, "duration_days": 30}
        )
        self.gold, _ = Plan.objects.get_or_create(
            code="gold",
            defaults={"name": "Gold Plan", "price": 1999.00, "duration_days": 60}
        )

    def test_double_approval_leaves_expiry_unchanged(self):
        order = PaymentOrder.objects.create(
            user=self.user, plan=self.silver, amount=self.silver.price, status='pending'
        )
        order.activate_subscription()
        self.user.refresh_from_db()
        first_expiry = self.user.subscription.expires_at

        # Call approve/activate again on same order
        order.activate_subscription()
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription.expires_at, first_expiry)

    def test_admin_edit_notes_does_not_extend_expiry(self):
        from payments.admin import PaymentOrderAdmin
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        order = PaymentOrder.objects.create(
            user=self.user, plan=self.silver, amount=self.silver.price, status='pending'
        )
        order.activate_subscription()
        self.user.refresh_from_db()
        first_expiry = self.user.subscription.expires_at

        # Simulate admin editing admin_notes
        admin = PaymentOrderAdmin(PaymentOrder, AdminSite())
        request = RequestFactory().post('/admin/payments/paymentorder/')
        request.user = self.user

        class MockForm:
            changed_data = ['admin_notes']

        order.admin_notes = "Updated note by admin"
        admin.save_model(request, order, MockForm(), change=True)

        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription.expires_at, first_expiry)

    def test_approve_rejected_order(self):
        order = PaymentOrder.objects.create(
            user=self.user, plan=self.silver, amount=self.silver.price, status='rejected'
        )
        order.approve()
        self.user.refresh_from_db()
        self.assertTrue(self.user.subscription.is_active)
        self.assertEqual(order.status, 'completed')

    def test_upgrade_and_renewal_expiry_logic(self):
        # Silver activation (30 days)
        order1 = PaymentOrder.objects.create(
            user=self.user, plan=self.silver, amount=self.silver.price, status='pending'
        )
        order1.activate_subscription()
        self.user.refresh_from_db()
        silver_expiry = self.user.subscription.expires_at

        # Renewing silver (same plan) extends previous expiry by 30 days
        order2 = PaymentOrder.objects.create(
            user=self.user, plan=self.silver, amount=self.silver.price, status='pending'
        )
        order2.activate_subscription()
        self.user.refresh_from_db()
        renewal_expiry = self.user.subscription.expires_at
        self.assertAlmostEqual(
            (renewal_expiry - silver_expiry).total_seconds(),
            30 * 86400,
            delta=5
        )

        # Upgrading to Gold (different plan) starts fresh from now, not extending silver
        order3 = PaymentOrder.objects.create(
            user=self.user, plan=self.gold, amount=self.gold.price, status='pending'
        )
        order3.activate_subscription()
        self.user.refresh_from_db()
        gold_expiry = self.user.subscription.expires_at
        from django.utils import timezone
        now = timezone.now()
        self.assertAlmostEqual(
            (gold_expiry - now).total_seconds(),
            self.gold.duration_days * 86400,
            delta=5
        )

    def test_reject_active_order_resets_subscription(self):
        order = PaymentOrder.objects.create(
            user=self.user, plan=self.silver, amount=self.silver.price, status='pending'
        )
        order.activate_subscription()
        self.user.refresh_from_db()
        self.assertTrue(self.user.subscription.is_active)

        order.reject()
        order.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(order.status, 'rejected')
        self.assertFalse(self.user.subscription.is_active)
        self.assertEqual(self.user.subscription.plan_type, 'Free')

    def test_user_with_no_orders_has_free_subscription(self):
        new_user = CustomUser.objects.create_user(
            username="no_orders_user",
            email="no_orders@test.com",
            password="TestPassword123!",
            full_name="No Orders",
            gender="F",
            phone_number="9876543212",
        )
        self.assertFalse(new_user.subscription.is_active)
        self.assertEqual(new_user.subscription.plan_type, 'Free')
        self.assertIsNone(new_user.subscription.expires_at)
        self.assertIn("no_orders_user", str(new_user.subscription))

    def test_str_representation_when_user_is_none(self):
        order = PaymentOrder.objects.create(
            user=None, plan=self.silver, amount=self.silver.price, status='pending'
        )
        order_str = str(order)
        self.assertIn("Deleted User", order_str)
        self.assertIn("Silver Plan", order_str)

    def test_reject_fallback_to_expired_order_resets_to_free(self):
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()

        # Order 1: Silver approved 40 days ago (30-day plan, so expired 10 days ago)
        order1 = PaymentOrder.objects.create(
            user=self.user, plan=self.silver, amount=self.silver.price, status='pending'
        )
        order1.approve()
        order1.verified_at = now - timedelta(days=40)
        order1.save(update_fields=['verified_at'])

        # Order 2: Gold approved today
        order2 = PaymentOrder.objects.create(
            user=self.user, plan=self.gold, amount=self.gold.price, status='pending'
        )
        order2.approve()
        self.user.refresh_from_db()
        self.assertTrue(self.user.subscription.is_active)
        self.assertEqual(self.user.subscription.plan_type, self.gold.name)

        # Reject Order 2: since Order 1 is expired, subscription must reset to Free!
        order2.reject()
        self.user.refresh_from_db()
        self.assertFalse(self.user.subscription.is_active)
        self.assertEqual(self.user.subscription.plan_type, 'Free')
        self.assertIsNone(self.user.subscription.expires_at)

    def test_reject_fallback_to_valid_order_preserves_original_expiry(self):
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()

        # Order 1: Silver approved 10 days ago (30-day plan, so 20 days left)
        order1 = PaymentOrder.objects.create(
            user=self.user, plan=self.silver, amount=self.silver.price, status='pending'
        )
        order1.approve()
        order1.verified_at = now - timedelta(days=10)
        order1.save(update_fields=['verified_at'])
        expected_expiry = order1.verified_at + timedelta(days=self.silver.duration_days)

        # Order 2: Gold approved today
        order2 = PaymentOrder.objects.create(
            user=self.user, plan=self.gold, amount=self.gold.price, status='pending'
        )
        order2.approve()

        # Reject Order 2: fallback to Order 1 with its original expiry (not extending or restarting today)
        order2.reject()
        self.user.refresh_from_db()
        order1.refresh_from_db()
        self.assertEqual(order1.status, 'completed')
        self.assertTrue(self.user.subscription.is_active)
        self.assertEqual(self.user.subscription.plan_type, self.silver.name)
        self.assertEqual(self.user.subscription.active_order, order1)
        self.assertAlmostEqual(
            (self.user.subscription.expires_at - expected_expiry).total_seconds(),
            0,
            delta=2
        )


