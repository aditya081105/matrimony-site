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

    def test_profile_list_bounded_queries(self):
        from users.models import City, Caste
        from django.urls import reverse
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        city = City.objects.create(name="Siwan N1 City")
        caste = Caste.objects.create(name="N1 Caste")

        viewer = User.objects.create_user(
            username="n1viewer",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=True,
            gender='M'
        )

        for i in range(5):
            User.objects.create_user(
                username=f"n1target_{i}",
                password="TestPass123!",
                is_approved=True,
                is_email_verified=True,
                gender='F',
                city=city,
                caste_community=caste
            )

        self.client.login(username="n1viewer", password="TestPass123!")

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('profile_list'))
            self.assertEqual(response.status_code, 200)

        # Profile queries must be bounded and not suffer from per-row N+1 explosion
        self.assertLessEqual(len(queries), 15)

    def test_view_profile_unapproved_access_blocked(self):
        from django.urls import reverse

        unapproved = User.objects.create_user(
            username="unapproved_target",
            password="TestPass123!",
            is_approved=False,
            is_email_verified=True,
            gender='F'
        )

        viewer = User.objects.create_user(
            username="normal_viewer",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=True,
            gender='M'
        )

        self.client.login(username="normal_viewer", password="TestPass123!")
        response = self.client.get(reverse('view_profile', args=[unapproved.id]))
        # Must redirect back to profile list and not expose details
        self.assertEqual(response.status_code, 302)

    def test_verify_email_with_timestamp_signer(self):
        from django.urls import reverse
        from django.core.signing import TimestampSigner

        unverified = User.objects.create_user(
            username="signer_test_user",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=False
        )

        signer = TimestampSigner()
        valid_token = signer.sign(unverified.id)

        response = self.client.get(reverse('verify_email', args=[valid_token]))
        self.assertEqual(response.status_code, 302)
        unverified.refresh_from_db()
        self.assertTrue(unverified.is_email_verified)

    def test_contact_form_submission(self):
        from django.urls import reverse
        response = self.client.post(reverse('contact_us'), {
            'name': 'Test Submitter',
            'email': 'submitter@example.com',
            'message': 'Testing contact submission asynchronously',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your message has been sent successfully.")

    def test_profile_list_gender_filter_defaults_and_explicit(self):
        from django.urls import reverse

        male_user = User.objects.create_user(
            username="male_viewer",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=True,
            gender='M'
        )
        female_user = User.objects.create_user(
            username="female_viewer",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=True,
            gender='F'
        )
        target_m = User.objects.create_user(
            username="target_male",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=True,
            gender='M'
        )
        target_f = User.objects.create_user(
            username="target_female",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=True,
            gender='F'
        )

        # 1. Male user visits without GET params -> defaults to Female ('F')
        self.client.login(username="male_viewer", password="TestPass123!")
        res = self.client.get(reverse('profile_list'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['selected_gender'], 'F')
        profile_ids = [p.id for p in res.context['page_obj']]
        self.assertIn(target_f.id, profile_ids)
        self.assertNotIn(target_m.id, profile_ids)

        # 2. Female user visits without GET params -> defaults to Male ('M')
        self.client.login(username="female_viewer", password="TestPass123!")
        res = self.client.get(reverse('profile_list'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['selected_gender'], 'M')
        profile_ids = [p.id for p in res.context['page_obj']]
        self.assertIn(target_m.id, profile_ids)
        self.assertNotIn(target_f.id, profile_ids)

        # 3. Explicit 'any' filter -> shows both genders
        res_any = self.client.get(reverse('profile_list'), {'gender': 'any'})
        self.assertEqual(res_any.status_code, 200)
        self.assertEqual(res_any.context['selected_gender'], 'any')
        profile_ids_any = [p.id for p in res_any.context['page_obj']]
        self.assertIn(target_m.id, profile_ids_any)
        self.assertIn(target_f.id, profile_ids_any)

        # 4. Explicit 'F' filter for female user
        res_f = self.client.get(reverse('profile_list'), {'gender': 'F'})
        self.assertEqual(res_f.status_code, 200)
        self.assertEqual(res_f.context['selected_gender'], 'F')
        profile_ids_f = [p.id for p in res_f.context['page_obj']]
        self.assertIn(target_f.id, profile_ids_f)
        self.assertNotIn(target_m.id, profile_ids_f)

    def test_admin_account_hidden_from_regular_users(self):
        from django.urls import reverse

        admin_user = User.objects.create_superuser(
            username="secret_admin",
            email="admin@test.com",
            password="AdminPass123!",
            is_staff=True,
            is_superuser=True,
            is_approved=True,
            is_email_verified=True,
            gender='M',
            full_name="Secret Admin"
        )

        normal_user = User.objects.create_user(
            username="normal_member",
            password="MemberPass123!",
            is_approved=True,
            is_email_verified=True,
            gender='F'
        )

        self.client.login(username="normal_member", password="MemberPass123!")

        # 1. Admin must not appear in profile_list
        res = self.client.get(reverse('profile_list'), {'gender': 'any'})
        self.assertEqual(res.status_code, 200)
        profile_ids = [p.id for p in res.context['page_obj']]
        self.assertNotIn(admin_user.id, profile_ids)

        # 2. Regular user cannot view admin profile directly
        view_res = self.client.get(reverse('view_profile', args=[admin_user.id]))
        self.assertEqual(view_res.status_code, 302)

    def test_admin_viewer_can_view_all_profiles_with_contact_details(self):
        from django.urls import reverse

        admin_user = User.objects.create_superuser(
            username="super_viewer_admin",
            email="superadmin@test.com",
            password="AdminPass123!",
            is_staff=True,
            is_superuser=True,
            is_approved=False,       # Unapproved admin account
            is_email_verified=False  # Unverified admin account
        )

        suspended_target = User.objects.create_user(
            username="suspended_user",
            password="Pass123!",
            full_name="Suspended Person",
            phone_number="9876543210",
            email="suspended@example.com",
            is_approved=True,
            is_suspended=True,
            gender='F'
        )

        unapproved_target = User.objects.create_user(
            username="unapproved_user",
            password="Pass123!",
            full_name="Unapproved Person",
            phone_number="9123456789",
            email="unapproved@example.com",
            is_approved=False,
            gender='M'
        )

        self.client.login(username="super_viewer_admin", password="AdminPass123!")

        # 1. Admin can access profile_list without being blocked by unapproved/unverified status
        res_list = self.client.get(reverse('profile_list'))
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(res_list.context['selected_gender'], 'any')

        # 2. Admin can view suspended profile and see contact details
        res_suspended = self.client.get(reverse('view_profile', args=[suspended_target.id]))
        self.assertEqual(res_suspended.status_code, 200)
        self.assertContains(res_suspended, "9876543210")
        self.assertContains(res_suspended, "Administrator Moderation View")

        # 3. Admin can view unapproved profile and see contact details
        res_unapproved = self.client.get(reverse('view_profile', args=[unapproved_target.id]))
        self.assertEqual(res_unapproved.status_code, 200)
        self.assertContains(res_unapproved, "9123456789")
        self.assertContains(res_unapproved, "Administrator Moderation View")

    def test_unique_email_and_disposable_email_blocked(self):
        from users.forms import UserRegisterForm, UserUpdateForm

        User.objects.create_user(
            username="existing_member",
            email="rahulkumar@gmail.com",
            password="ValidPassword123!"
        )

        base_data = {
            'username': 'new_member',
            'full_name': 'New Member',
            'gender': 'M',
            'phone_number': '9876543210',
            'date_of_birth': '1998-05-15',
            'password1': 'ValidPassword123!',
            'password2': 'ValidPassword123!',
        }

        # 1. Exact duplicate email blocked (case-insensitive)
        form_dup = UserRegisterForm(data={**base_data, 'email': 'RahulKumar@gmail.com'})
        self.assertFalse(form_dup.is_valid())
        self.assertIn('email', form_dup.errors)

        # 2. Gmail dot variation duplicate blocked
        form_dot = UserRegisterForm(data={**base_data, 'email': 'rahul.kumar@gmail.com'})
        self.assertFalse(form_dot.is_valid())
        self.assertIn('email', form_dot.errors)

        # 3. Plus alias blocked
        form_plus = UserRegisterForm(data={**base_data, 'email': 'newuser+spam@gmail.com'})
        self.assertFalse(form_plus.is_valid())
        self.assertIn('email', form_plus.errors)

        # 4. Disposable / temporary email domains blocked
        for temp_email in (
            'user@temp-mail.org',
            'user@yopmail.com',
            'user@10minutemail.com',
            'user@mailinator.com',
            'user@sharklasers.com',
            'user@sub.tempmail.com',
            'user@burnerdomain.tk',
            'user@gmai1.com',
        ):
            form_temp = UserRegisterForm(data={**base_data, 'email': temp_email})
            self.assertFalse(form_temp.is_valid(), f"Disposable email {temp_email} should be rejected")
            self.assertIn('email', form_temp.errors)

        # 5. Legitimate unique email succeeds
        form_valid = UserRegisterForm(data={**base_data, 'email': 'genuine.person@gmail.com'})
        self.assertTrue(form_valid.is_valid(), form_valid.errors)