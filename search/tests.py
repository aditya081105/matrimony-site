from django.test import TestCase
from django.urls import reverse
from users.models import CustomUser


class SearchTests(TestCase):
    def setUp(self):
        self.user1 = CustomUser.objects.create_user(
            username="user_search1",
            email="search1@test.com",
            password="TestPassword123!",
            full_name="Rohit Sharma",
            gender="M",
            occupation="Software Engineer",
            is_approved=True,
            is_active=True,
        )
        self.user2 = CustomUser.objects.create_user(
            username="user_search2",
            email="search2@test.com",
            password="TestPassword123!",
            full_name="Pooja Verma",
            gender="F",
            occupation="Doctor",
            is_approved=True,
            is_active=True,
        )
        self.client.login(username="user_search1", password="TestPassword123!")

    def test_search_view_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('search_profiles'))
        self.assertEqual(response.status_code, 302)

    def test_search_matches_query(self):
        response = self.client.get(reverse('search_profiles'), {'q': 'Doctor'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pooja Verma")

    def test_search_no_match(self):
        response = self.client.get(reverse('search_profiles'), {'q': 'NonExistentPerson'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No profiles matched")

    def test_search_excludes_suspended(self):
        self.user2.is_suspended = True
        self.user2.save()
        response = self.client.get(reverse('search_profiles'), {'q': 'Doctor'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Pooja Verma")

    def test_search_matches_open_caste_and_sub_caste(self):
        self.user2.caste = "Brahmin"
        self.user2.sub_caste = "Mishra"
        self.user2.save()

        # Search by caste
        response = self.client.get(reverse('search_profiles'), {'q': 'Brahmin'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pooja Verma")

        # Search by sub-caste
        response2 = self.client.get(reverse('search_profiles'), {'q': 'Mishra'})
        self.assertEqual(response2.status_code, 200)
        self.assertContains(response2, "Pooja Verma")
