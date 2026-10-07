from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()

class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            username="testuser",
            password="TestPass123!"
        )

        self.assertEqual(user.username, "testuser")
        self.assertTrue(user.check_password("TestPass123!"))

    def test_user_age_property(self):
        from datetime import date
        today = date.today()
        user = User.objects.create_user(
            username="ageuser",
            password="TestPass123!",
            date_of_birth=date(today.year - 25, today.month, today.day)
        )
        self.assertEqual(user.age, 25)

    def test_user_update_form_preserves_dob_and_syncs_profile(self):
        from datetime import date
        from users.forms import UserUpdateForm
        from users.models import City
        city = City.objects.create(name="Patna")
        user = User.objects.create_user(
            username="profileuser",
            password="TestPass123!",
            phone_number="9876543210",
            date_of_birth=date(1995, 5, 10),
            full_name="Profile User",
        )
        form_data = {
            'full_name': 'Profile User Updated',
            'email': 'updated@test.com',
            'gender': 'M',
            'phone_number': '9876543210',
            'date_of_birth': '1995-05-10',
            'occupation': 'Architect',
            'height_cm': 175,
            'city': city.id,
            'bio': 'Test bio here',
            'father_name': 'Father Test',
            'mother_name': 'Mother Test',
            'address': 'Main Street 123',
        }
        form = UserUpdateForm(data=form_data, instance=user)
        self.assertTrue(form.is_valid(), form.errors)
        saved_user = form.save()

        # Date of birth must NOT be wiped out
        self.assertEqual(saved_user.date_of_birth, date(1995, 5, 10))

        # Profile must be synced
        self.assertEqual(saved_user.profile.father_name, 'Father Test')
        self.assertEqual(saved_user.profile.mother_name, 'Mother Test')
        self.assertEqual(saved_user.profile.city_hometown, city)
        self.assertEqual(saved_user.profile.bio, 'Test bio here')

    def test_caste_and_sub_caste_properties(self):
        from users.models import Caste
        user1 = User.objects.create_user(
            username="casteuser1",
            password="TestPass123!",
            caste="Rajput",
            sub_caste="Chauhan"
        )
        self.assertEqual(user1.display_caste, "Rajput (Chauhan)")

        user2 = User.objects.create_user(
            username="casteuser2",
            password="TestPass123!",
            caste="Brahmin"
        )
        self.assertEqual(user2.display_caste, "Brahmin")

        legacy_caste = Caste.objects.create(name="Yadav")
        user3 = User.objects.create_user(
            username="casteuser3",
            password="TestPass123!",
            caste_community=legacy_caste
        )
        self.assertEqual(user3.display_caste, "Yadav")

    def test_user_update_form_open_caste_fields(self):
        from users.forms import UserUpdateForm
        user = User.objects.create_user(
            username="updatecaste",
            password="TestPass123!",
            phone_number="9123456789",
        )
        form_data = {
            'full_name': 'Caste Tester',
            'email': 'caste@test.com',
            'gender': 'M',
            'phone_number': '9123456789',
            'caste': 'Kushwaha',
            'sub_caste': 'Maurya',
        }
        form = UserUpdateForm(data=form_data, instance=user)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.caste, 'Kushwaha')
        self.assertEqual(saved.sub_caste, 'Maurya')
        self.assertEqual(saved.display_caste, 'Kushwaha (Maurya)')

    def test_phone_number_legitimacy_validation(self):
        from users.forms import UserRegisterForm
        # Invalid start digit (not 6,7,8,9)
        form1 = UserRegisterForm(data={'phone_number': '1234567890'})
        self.assertFalse(form1.is_valid())
        self.assertIn('phone_number', form1.errors)

        # Invalid repetitive dummy numbers (e.g. 0000000000)
        form2 = UserRegisterForm(data={'phone_number': '0000000000'})
        self.assertFalse(form2.is_valid())
        self.assertIn('phone_number', form2.errors)

        # Invalid length
        form3 = UserRegisterForm(data={'phone_number': '98765'})
        self.assertFalse(form3.is_valid())
        self.assertIn('phone_number', form3.errors)

    def test_resend_verification_email_rate_limited(self):
        from django.urls import reverse
        import time

        user = User.objects.create_user(
            username="verifyrateuser",
            password="TestPass123!",
            email="rateuser@example.com",
            is_email_verified=False
        )
        self.client.login(username="verifyrateuser", password="TestPass123!")

        # First request sends email and sets session timestamp
        response1 = self.client.get(reverse('resend_verification'))
        self.assertEqual(response1.status_code, 302)

        # Immediate second request should be blocked by 60s cooldown
        response2 = self.client.get(reverse('resend_verification'), follow=True)
        self.assertEqual(response2.status_code, 200)
        messages_list = list(response2.context['messages'])
        self.assertTrue(any('sent recently' in str(m) for m in messages_list))