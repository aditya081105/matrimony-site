from django.test import TestCase, TransactionTestCase, Client, skipUnlessDBFeature
from django.db import connection
from django.urls import reverse
import threading
from users.models import CustomUser, City
from communications.models import (
    Block,
    ContactRequest,
    RequestAttempt,
    SavedProfile,
    ActivityLog,
)


class CommunicationTests(TestCase):
    def setUp(self):
        self.city = City.objects.create(name="Delhi")

        self.user1 = CustomUser.objects.create_user(
            username="user1",
            email="user1@test.com",
            password="Test12345!",
            full_name="User One",
            gender="M",
            phone_number="9999999999",
            is_approved=True,
            is_email_verified=True,
            date_of_birth="2000-01-01",
            height_cm=170,
            city=self.city,
            profile_photo="test.jpg",
        )

        self.user2 = CustomUser.objects.create_user(
            username="user2",
            email="user2@test.com",
            password="Test12345!",
            full_name="User Two",
            gender="F",
            phone_number="8888888888",
            is_approved=True,
            is_email_verified=True,
            date_of_birth="2000-01-01",
            height_cm=165,
            city=self.city,
            profile_photo="test.jpg",
        )

        self.client.login(username="user1", password="Test12345!")

    def test_cannot_send_request_to_self(self):
        self.client.post(reverse("send_request", args=[self.user1.id]))

        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_blocked_user_cannot_send_request(self):
        Block.objects.create(
            blocker=self.user2,
            blocked=self.user1,
        )

        self.client.post(reverse("send_request", args=[self.user2.id]))

        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_unblock_removes_block(self):
        Block.objects.create(
            blocker=self.user1,
            blocked=self.user2,
        )

        self.client.post(reverse("unblock_user", args=[self.user2.id]))

        self.assertFalse(
            Block.objects.filter(
                blocker=self.user1,
                blocked=self.user2,
            ).exists()
        )

    def test_toggle_save(self):
        self.client.post(reverse("toggle_save", args=[self.user2.id]))

        self.assertEqual(SavedProfile.objects.count(), 1)

        self.client.post(reverse("toggle_save", args=[self.user2.id]))

        self.assertEqual(SavedProfile.objects.count(), 0)

    def test_duplicate_request_not_created(self):
        ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status="pending",
            attempt_count=1,
        )

        response = self.client.post(
            reverse("send_request", args=[self.user2.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactRequest.objects.count(), 1)

    def test_request_allowed_before_daily_limit(self):
        for _ in range(2):
            RequestAttempt.objects.create(
                sender=self.user1,
                receiver=self.user2,
            )

        response = self.client.post(
            reverse("send_request", args=[self.user2.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactRequest.objects.count(), 1)

    def test_duplicate_request_returns_redirect(self):
        ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status="pending",
            attempt_count=1,
        )

        response = self.client.post(
            reverse("send_request", args=[self.user2.id])
        )

        self.assertEqual(response.status_code, 302)

    def test_request_blocked_at_daily_limit(self):
        for _ in range(3):
            RequestAttempt.objects.create(
                sender=self.user1,
                receiver=self.user2,
            )

        self.client.post(reverse("send_request", args=[self.user2.id]))

        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_mutual_request_auto_matches(self):
        # User 2 sends request to User 1
        ContactRequest.objects.create(
            sender=self.user2,
            receiver=self.user1,
            status='pending',
            attempt_count=1,
        )
        # User 1 sends request to User 2 -> auto match!
        response = self.client.post(reverse("send_request", args=[self.user2.id]))
        self.assertEqual(response.status_code, 302)

        # Both requests should now be accepted
        req_2_to_1 = ContactRequest.objects.get(sender=self.user2, receiver=self.user1)
        self.assertEqual(req_2_to_1.status, 'accepted')

    def test_unmatch_logs_activity(self):
        ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status='accepted',
        )
        self.client.post(reverse("unmatch", args=[self.user2.id]))
        self.assertEqual(ContactRequest.objects.count(), 0)
        self.assertTrue(ActivityLog.objects.filter(user=self.user1, target_user=self.user2, action='unmatch').exists())

    def test_block_removes_saved_profiles_bidirectionally(self):
        SavedProfile.objects.create(user=self.user1, saved_user=self.user2)
        SavedProfile.objects.create(user=self.user2, saved_user=self.user1)
        self.client.post(reverse("block_user", args=[self.user2.id]))
        self.assertEqual(SavedProfile.objects.count(), 0)

    def test_state_mutating_endpoints_reject_get_requests(self):
        # Enforce HTTP 405 Method Not Allowed on plain GET requests
        for endpoint, args in [
            ("send_request", [self.user2.id]),
            ("block_user", [self.user2.id]),
            ("unblock_user", [self.user2.id]),
            ("unmatch", [self.user2.id]),
            ("cancel_request", [self.user2.id]),
            ("toggle_save", [self.user2.id]),
        ]:
            response = self.client.get(reverse(endpoint, args=args))
            self.assertEqual(
                response.status_code, 405,
                f"Endpoint {endpoint} allowed GET but must require POST"
            )


@skipUnlessDBFeature('has_select_for_update')
class CommunicationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.city = City.objects.create(name="Delhi")
        self.user1 = CustomUser.objects.create_user(
            username="concurrent_user1",
            email="concurrent1@test.com",
            password="Test12345!",
            full_name="User One",
            gender="M",
            phone_number="9999999991",
            is_approved=True,
            is_email_verified=True,
            date_of_birth="2000-01-01",
            height_cm=170,
            city=self.city,
            profile_photo="test.jpg",
        )
        self.user2 = CustomUser.objects.create_user(
            username="concurrent_user2",
            email="concurrent2@test.com",
            password="Test12345!",
            full_name="User Two",
            gender="F",
            phone_number="8888888882",
            is_approved=True,
            is_email_verified=True,
            date_of_birth="2000-01-01",
            height_cm=165,
            city=self.city,
            profile_photo="test.jpg",
        )
        self.user3 = CustomUser.objects.create_user(
            username="concurrent_user3",
            email="concurrent3@test.com",
            password="Test12345!",
            full_name="User Three",
            gender="F",
            phone_number="8888888883",
            is_approved=True,
            is_email_verified=True,
            date_of_birth="2000-01-01",
            height_cm=165,
            city=self.city,
            profile_photo="test.jpg",
        )
        self.user4 = CustomUser.objects.create_user(
            username="concurrent_user4",
            email="concurrent4@test.com",
            password="Test12345!",
            full_name="User Four",
            gender="F",
            phone_number="8888888884",
            is_approved=True,
            is_email_verified=True,
            date_of_birth="2000-01-01",
            height_cm=165,
            city=self.city,
            profile_photo="test.jpg",
        )

    def test_concurrent_quota_race_condition_prevention(self):
        # User 1 is on free tier (daily limit = 3).
        # Pre-populate 2 attempts so only 1 attempt remains.
        RequestAttempt.objects.create(sender=self.user1, receiver=self.user4)
        RequestAttempt.objects.create(sender=self.user1, receiver=self.user4)

        errors = []
        clients = []
        for _ in range(2):
            c = Client()
            c.force_login(self.user1)
            clients.append(c)

        targets = [self.user2, self.user3]

        def attempt_send(c, target):
            try:
                c.post(reverse("send_request", args=[target.id]))
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        threads = [
            threading.Thread(target=attempt_send, args=(clients[i], targets[i]))
            for i in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        # Exactly 3 total daily attempts allowed (2 initial + 1 successful from threads)
        self.assertEqual(RequestAttempt.objects.filter(sender=self.user1).count(), 3)
        # Exactly 1 new ContactRequest created (the other was rejected by quota)
        self.assertEqual(
            ContactRequest.objects.filter(sender=self.user1).filter(
                receiver__in=[self.user2, self.user3]
            ).count(),
            1
        )