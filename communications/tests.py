from django.test import TestCase
from django.urls import reverse

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
        self.client.get(reverse("send_request", args=[self.user1.id]))

        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_blocked_user_cannot_send_request(self):
        Block.objects.create(
            blocker=self.user2,
            blocked=self.user1,
        )

        self.client.get(reverse("send_request", args=[self.user2.id]))

        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_unblock_removes_block(self):
        Block.objects.create(
            blocker=self.user1,
            blocked=self.user2,
        )

        self.client.get(reverse("unblock_user", args=[self.user2.id]))

        self.assertFalse(
            Block.objects.filter(
                blocker=self.user1,
                blocked=self.user2,
            ).exists()
        )

    def test_toggle_save(self):
        self.client.get(reverse("toggle_save", args=[self.user2.id]))

        self.assertEqual(SavedProfile.objects.count(), 1)

        self.client.get(reverse("toggle_save", args=[self.user2.id]))

        self.assertEqual(SavedProfile.objects.count(), 0)

    def test_duplicate_request_not_created(self):
        ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status="pending",
            attempt_count=1,
        )

        response = self.client.get(
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

        response = self.client.get(
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

        response = self.client.get(
            reverse("send_request", args=[self.user2.id])
        )

        self.assertEqual(response.status_code, 302)

    def test_request_blocked_at_daily_limit(self):
        for _ in range(3):
            RequestAttempt.objects.create(
                sender=self.user1,
                receiver=self.user2,
            )

        self.client.get(reverse("send_request", args=[self.user2.id]))

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
        response = self.client.get(reverse("send_request", args=[self.user2.id]))
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
        self.client.get(reverse("unmatch", args=[self.user2.id]))
        self.assertEqual(ContactRequest.objects.count(), 0)
        self.assertTrue(ActivityLog.objects.filter(user=self.user1, target_user=self.user2, action='unmatch').exists())

    def test_block_removes_saved_profiles_bidirectionally(self):
        SavedProfile.objects.create(user=self.user1, saved_user=self.user2)
        SavedProfile.objects.create(user=self.user2, saved_user=self.user1)
        self.client.get(reverse("block_user", args=[self.user2.id]))
        self.assertEqual(SavedProfile.objects.count(), 0)