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
            is_email_verified=True,
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
            is_email_verified=True,
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

    def test_search_excludes_admin_and_staff(self):
        CustomUser.objects.create_user(
            username="admin_doctor",
            email="admindoctor@test.com",
            password="TestPassword123!",
            full_name="Dr. Administrator",
            gender="M",
            occupation="Doctor",
            is_staff=True,
            is_approved=True,
            is_active=True,
        )

        response = self.client.get(reverse('search_profiles'), {'q': 'Doctor'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pooja Verma")
        self.assertNotContains(response, "Dr. Administrator")

    def test_admin_can_search_all_members(self):
        admin = CustomUser.objects.create_superuser(
            username="search_admin",
            email="searchadmin@test.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=True
        )

        self.user2.is_suspended = True
        self.user2.save()

        self.client.login(username="search_admin", password="AdminPassword123!")
        response = self.client.get(reverse('search_profiles'), {'q': 'Doctor'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pooja Verma")

    def test_search_htmx_partial_render(self):
        response = self.client.get(
            reverse('search_profiles'),
            {'q': 'Doctor'},
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'search/includes/results_list.html')
        self.assertTemplateNotUsed(response, 'base.html')
        self.assertContains(response, "Pooja Verma")
        self.assertContains(response, 'contact-action-')

    def test_search_blocked_for_unverified_user(self):
        self.user1.is_email_verified = False
        self.user1.save()
        response = self.client.get(reverse('search_profiles'))
        self.assertContains(response, "Verify Your Email")
        self.assertNotContains(response, "Pooja Verma")

    def test_search_blocked_for_unapproved_user(self):
        self.user1.is_approved = False
        self.user1.save()
        response = self.client.get(reverse('search_profiles'))
        self.assertContains(response, "Pending Approval")
        self.assertNotContains(response, "Pooja Verma")

    def test_search_blocked_for_suspended_user(self):
        self.user1.is_suspended = True
        self.user1.save()
        response = self.client.get(reverse('search_profiles'))
        self.assertEqual(response.status_code, 302)
