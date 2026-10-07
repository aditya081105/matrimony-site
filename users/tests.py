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