from django.test import TestCase
from django.urls import reverse

from users.models import CustomUser, City
from communications.models import (
    Block,
    ContactRequest,
    RequestAttempt,
    SavedProfile,
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
            profile_photo="test.jpg"
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
            profile_photo="test.jpg"
        )


    def test_cannot_send_request_to_self(self):
        self.client.login(username="user1", password="Test12345!")

        self.client.get(reverse("send_request", args=[self.user1.id]))

        self.assertEqual(ContactRequest.objects.count(), 0)


    def test_blocked_user_cannot_send_request(self):
        self.client.login(username="user1", password="Test12345!")

        Block.objects.create(
            blocker=self.user2,
            blocked=self.user1
        )

        self.client.get(reverse("send_request", args=[self.user2.id]))

        self.assertEqual(ContactRequest.objects.count(), 0)


    def test_unblock_removes_block(self):
        self.client.login(username="user1", password="Test12345!")

        Block.objects.create(
            blocker=self.user1,
            blocked=self.user2
        )

        self.client.get(reverse("unblock_user", args=[self.user2.id]))

        self.assertFalse(
            Block.objects.filter(
                blocker=self.user1,
                blocked=self.user2
            ).exists()
        )


    def test_toggle_save(self):
        self.client.login(username="user1", password="Test12345!")

        self.client.get(reverse("toggle_save", args=[self.user2.id]))

        self.assertEqual(SavedProfile.objects.count(), 1)

        self.client.get(reverse("toggle_save", args=[self.user2.id]))

        self.assertEqual(SavedProfile.objects.count(), 0)


    def test_duplicate_request_not_created(self):
        self.client.login(username="user1", password="Test12345!")

        ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status="pending",
            attempt_count=1
        )

        response = self.client.get(
            reverse("send_request", args=[self.user2.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactRequest.objects.count(), 1)


    def test_request_allowed_before_daily_limit(self):
        self.client.login(username="user1", password="Test12345!")

        for _ in range(2):
            RequestAttempt.objects.create(
                sender=self.user1,
                receiver=self.user2
            )

        response = self.client.get(
            reverse("send_request", args=[self.user2.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactRequest.objects.count(), 1)


    def test_duplicate_request_returns_redirect(self):
        self.client.login(username="user1", password="Test12345!")

        ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status="pending",
            attempt_count=1
        )

        response = self.client.get(
            reverse("send_request", args=[self.user2.id])
        )

        self.assertEqual(response.status_code, 302)


    def test_request_blocked_at_daily_limit(self):
        self.client.login(username="user1", password="Test12345!")

        for _ in range(3):
            RequestAttempt.objects.create(
                sender=self.user1,
                receiver=self.user2
            )

        response = self.client.get(reverse("send_request", args=[self.user2.id]))

        self.assertEqual(ContactRequest.objects.count(), 0)
        # optionally assert response redirects to an error/message page