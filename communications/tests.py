from django.test import TestCase
from users.models import CustomUser
from .models import Block, ContactRequest, SavedProfile


class CommunicationModelTests(TestCase):

    def setUp(self):
        self.user1 = CustomUser.objects.create_user(
            username="user1",
            email="user1@test.com",
            password="Test12345!"
        )

        self.user2 = CustomUser.objects.create_user(
            username="user2",
            email="user2@test.com",
            password="Test12345!"
        )

    def test_contact_request_creation(self):
        request = ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2
        )

        self.assertEqual(request.sender, self.user1)
        self.assertEqual(request.receiver, self.user2)
        self.assertEqual(request.status, "pending")

    def test_block_creation(self):
        block = Block.objects.create(
            blocker=self.user1,
            blocked=self.user2
        )

        self.assertEqual(block.blocker, self.user1)
        self.assertEqual(block.blocked, self.user2)

    def test_saved_profile_creation(self):
        saved = SavedProfile.objects.create(
            user=self.user1,
            saved_user=self.user2
        )

        self.assertEqual(saved.user, self.user1)
        self.assertEqual(saved.saved_user, self.user2)