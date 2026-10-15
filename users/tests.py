from django.test import TestCase
from django.urls import reverse
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
        # Must return 404 to prevent enumeration of unapproved accounts
        self.assertEqual(response.status_code, 404)

    def test_verify_email_with_timestamp_signer(self):
        from django.urls import reverse
        from django.core.signing import TimestampSigner

        unverified = User.objects.create_user(
            username="signer_test_user",
            email="signer@example.com",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=False
        )

        signer = TimestampSigner()
        valid_token = signer.sign(f"{unverified.id}:{unverified.email}")

        response = self.client.get(reverse('verify_email', args=[valid_token]))
        self.assertEqual(response.status_code, 302)
        unverified.refresh_from_db()
        self.assertTrue(unverified.is_email_verified)

    def test_legacy_bare_id_token_rejected(self):
        from django.urls import reverse
        from django.core.signing import TimestampSigner

        unverified = User.objects.create_user(
            username="legacy_token_user",
            email="legacy@example.com",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=False
        )

        signer = TimestampSigner()
        legacy_token = signer.sign(unverified.id)  # Bare ID without email binding

        response = self.client.get(reverse('verify_email', args=[legacy_token]))
        self.assertEqual(response.status_code, 302)
        unverified.refresh_from_db()
        self.assertFalse(unverified.is_email_verified)

    def test_contact_form_submission(self):
        from django.urls import reverse
        from django.core.cache import cache
        cache.clear()
        response = self.client.post(reverse('contact_us'), {
            'name': 'Test Submitter',
            'email': 'submitter@example.com',
            'message': 'Testing contact submission asynchronously',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your message has been sent successfully.")

    def test_contact_form_honeypot_discards_silently(self):
        from django.urls import reverse
        from django.core import mail
        from django.core.cache import cache
        cache.clear()
        mail.outbox.clear()

        response = self.client.post(reverse('contact_us'), {
            'name': 'Spam Bot',
            'email': 'bot@spammer.org',
            'message': 'Buy cheap meds now',
            'website_hp': 'http://spammer.org',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your message has been sent successfully.")
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_form_ip_rate_limiting(self):
        from django.urls import reverse
        from django.core import mail
        from django.core.cache import cache
        cache.clear()
        mail.outbox.clear()

        ip_env = {'REMOTE_ADDR': '198.51.100.42'}

        for i in range(3):
            response = self.client.post(reverse('contact_us'), {
                'name': f'Submitter {i}',
                'email': f'submitter{i}@example.com',
                'message': f'Message {i}',
            }, **ip_env)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Your message has been sent successfully.")

        self.assertEqual(len(mail.outbox), 3)

        # 4th request from same IP should be blocked
        blocked_response = self.client.post(reverse('contact_us'), {
            'name': 'Submitter 4',
            'email': 'submitter4@example.com',
            'message': 'Message 4',
        }, **ip_env)
        self.assertEqual(blocked_response.status_code, 200)
        self.assertContains(blocked_response, "Too many messages sent from your IP. Please try again later.")
        self.assertEqual(len(mail.outbox), 3)

    def test_contact_form_validation_bounds(self):
        from django.urls import reverse
        from django.core.cache import cache
        cache.clear()

        # Name too long
        res1 = self.client.post(reverse('contact_us'), {
            'name': 'A' * 101,
            'email': 'valid@example.com',
            'message': 'Hello world',
        })
        self.assertContains(res1, "Name must be 100 characters or fewer.")

        # Invalid email
        res2 = self.client.post(reverse('contact_us'), {
            'name': 'Valid Name',
            'email': 'not-an-email',
            'message': 'Hello world',
        })
        self.assertContains(res2, "Please enter a valid email address.")

        # Message too long
        res3 = self.client.post(reverse('contact_us'), {
            'name': 'Valid Name',
            'email': 'valid@example.com',
            'message': 'M' * 1001,
        })
        self.assertContains(res3, "Message must be 1,000 characters or fewer.")


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

    def test_profile_list_htmx_partial_render(self):
        viewer = User.objects.create_user(
            username="htmx_viewer",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=True,
            gender='M'
        )
        User.objects.create_user(
            username="target_female_htmx",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=True,
            is_active=True,
            gender='F',
            full_name="Target Female"
        )
        self.client.force_login(viewer)
        res = self.client.get(reverse('profile_list'), HTTP_HX_REQUEST="true")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'users/includes/profile_grid.html')
        self.assertTemplateNotUsed(res, 'base.html')
        self.assertContains(res, 'profile-card-col')
        self.assertContains(res, 'Target Female')

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

        # 2. Regular user cannot view admin profile directly (returns 404 to prevent staff ID enumeration oracle)
        view_res = self.client.get(reverse('view_profile', args=[admin_user.id]))
        self.assertEqual(view_res.status_code, 404)

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

        # 4. Disposable / temporary email domains blocked (including temp-mail.io rotating domains)
        for temp_email in (
            'user@temp-mail.org',
            'user@temp-mail.io',
            'user@daouse.com',
            'user@blondmail.com',
            'user@vintomaper.com',
            'user@fexbox.org',
            'user@randomthrowawaydomain.com',
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


class PasswordResetTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(
            username="resetuser",
            email="resetuser@gmail.com",
            password="OldPassword123!",
            full_name="Reset User"
        )

    def test_login_page_renders_forgot_password_link(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Forgot password?')
        self.assertContains(response, '/forgot-password/')

    def test_password_reset_request_valid_email(self):
        from django.core.cache import cache
        response = self.client.post('/forgot-password/', {'email': 'resetuser@gmail.com'})
        self.assertRedirects(response, '/forgot-password/verify/')
        
        cached_data = cache.get("pwd_reset_data_resetuser@gmail.com")
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data['user_id'], self.user.id)
        self.assertIn('code_hash', cached_data)
        self.assertEqual(len(cached_data['code_hash']), 64)
        # Ensure plaintext code is NEVER stored in cache
        self.assertNotIn('code', cached_data)

    def test_password_reset_verify_flow_and_confirm(self):
        from django.core import mail
        import re

        # 1. Request code
        self.client.post('/forgot-password/', {'email': 'resetuser@gmail.com'})
        self.assertTrue(len(mail.outbox) > 0)
        match = re.search(r'\b\d{6}\b', mail.outbox[-1].body)
        self.assertIsNotNone(match)
        valid_code = match.group(0)

        # 2. Enter wrong code
        bad_response = self.client.post('/forgot-password/verify/', {'action': 'verify', 'code': '000000'})
        self.assertEqual(bad_response.status_code, 200)
        self.assertContains(bad_response, 'Incorrect verification code')

        # 3. Enter correct code
        good_response = self.client.post('/forgot-password/verify/', {'action': 'verify', 'code': valid_code})
        self.assertRedirects(good_response, '/forgot-password/confirm/')

        # 4. Confirm new password with mismatch
        mismatch_res = self.client.post('/forgot-password/confirm/', {
            'new_password1': 'NewStrongPass123!',
            'new_password2': 'DifferentPass123!'
        })
        self.assertEqual(mismatch_res.status_code, 200)
        self.assertContains(mismatch_res, 'Passwords do not match')

        # 5. Confirm new password successfully
        success_res = self.client.post('/forgot-password/confirm/', {
            'new_password1': 'NewStrongPass123!',
            'new_password2': 'NewStrongPass123!'
        })
        self.assertRedirects(success_res, '/login/')

        # 6. Verify user can now authenticate with new password
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStrongPass123!'))
        self.assertFalse(self.user.check_password('OldPassword123!'))

    def test_password_reset_atomic_attempt_lockout(self):
        from django.core.cache import cache
        cache.clear()

        # Request code
        self.client.post('/forgot-password/', {'email': 'resetuser@gmail.com'})

        # 4 incorrect attempts
        for attempt in range(1, 5):
            res = self.client.post('/forgot-password/verify/', {'action': 'verify', 'code': '000000'})
            self.assertEqual(res.status_code, 200)
            self.assertContains(res, 'Incorrect verification code')

        # 5th incorrect attempt locks out and redirects to /forgot-password/
        res5 = self.client.post('/forgot-password/verify/', {'action': 'verify', 'code': '000000'})
        self.assertRedirects(res5, '/forgot-password/')
        self.assertIsNone(cache.get('pwd_reset_data_resetuser@gmail.com'))
        self.assertIsNone(cache.get('pwd_reset_attempts_resetuser@gmail.com'))

    def test_password_reset_hourly_rate_limit(self):
        from django.core.cache import cache
        cache.clear()

        # 5 requests within the hour (clearing 60s cooldown between requests)
        for i in range(5):
            cache.delete('pwd_reset_cooldown_resetuser@gmail.com')
            res = self.client.post('/forgot-password/', {'email': 'resetuser@gmail.com'})
            self.assertRedirects(res, '/forgot-password/verify/')

        # 6th request triggers hourly limit
        cache.delete('pwd_reset_cooldown_resetuser@gmail.com')
        res6 = self.client.post('/forgot-password/', {'email': 'resetuser@gmail.com'}, follow=True)
        self.assertContains(res6, 'Too many password reset requests for this email')



class ImageSecurityUploadTest(TestCase):
    def setUp(self):
        from users.validators import validate_image_file
        self.validate_image_file = validate_image_file

    def test_rejects_fake_image_script(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core.exceptions import ValidationError

        fake_file = SimpleUploadedFile(
            "fake_avatar.jpg",
            b"Plain text payload pretending to be a JPG image file",
            content_type="image/jpeg"
        )
        with self.assertRaises(ValidationError) as ctx:
            self.validate_image_file(fake_file)
        self.assertIn("not a valid image", str(ctx.exception))

    def test_rejects_oversized_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core.exceptions import ValidationError

        big_file = SimpleUploadedFile(
            "oversized.jpg",
            b"0" * (6 * 1024 * 1024),
            content_type="image/jpeg"
        )
        with self.assertRaises(ValidationError) as ctx:
            self.validate_image_file(big_file, max_size_mb=5)
        self.assertIn("under 5MB", str(ctx.exception))

    def test_accepts_valid_image(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        img_io = BytesIO()
        img = Image.new('RGB', (100, 100), color='crimson')
        img.save(img_io, format='JPEG')
        img_io.seek(0)

        valid_file = SimpleUploadedFile(
            "my_original_camera_photo_123.jpg",
            img_io.getvalue(),
            content_type="image/jpeg"
        )
        result = self.validate_image_file(valid_file)
        self.assertIsNotNone(result)
        self.assertTrue(result.name.endswith('.jpg'))
        # Original filename must be discarded and replaced with a random UUID
        self.assertNotEqual(result.name, "my_original_camera_photo_123.jpg")
        self.assertEqual(len(result.name), 36) # 32 hex chars + .jpg

    def test_old_photo_deleted_on_replacement_or_clear(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core.files.storage import default_storage
        from users.models import CustomUser
        from users.forms import UserUpdateForm

        user = CustomUser.objects.create_user(
            username='photouser',
            email='photouser@gmail.com',
            password='TestPassword123!',
            phone_number='9876543210'
        )

        def make_image_file(name):
            io = BytesIO()
            Image.new('RGB', (80, 80), color='blue').save(io, format='JPEG')
            io.seek(0)
            return SimpleUploadedFile(name, io.getvalue(), content_type='image/jpeg')

        # First upload
        form1 = UserUpdateForm(
            data={'full_name': 'Photo User', 'email': 'photouser@gmail.com', 'gender': 'M', 'phone_number': '9876543210'},
            files={'profile_photo': make_image_file('photo1.jpg')},
            instance=user
        )
        self.assertTrue(form1.is_valid(), form1.errors)
        u1 = form1.save()
        first_photo = u1.profile_photo.name
        self.assertTrue(default_storage.exists(first_photo))

        # Second upload (replace photo)
        form2 = UserUpdateForm(
            data={'full_name': 'Photo User', 'email': 'photouser@gmail.com', 'gender': 'M', 'phone_number': '9876543210'},
            files={'profile_photo': make_image_file('photo2.jpg')},
            instance=u1
        )
        self.assertTrue(form2.is_valid(), form2.errors)
        u2 = form2.save()
        second_photo = u2.profile_photo.name
        self.assertNotEqual(first_photo, second_photo)
        self.assertTrue(default_storage.exists(second_photo))
        # First photo must be deleted from disk
        self.assertFalse(default_storage.exists(first_photo))

        # Third step (clear photo)
        form3 = UserUpdateForm(
            data={'full_name': 'Photo User', 'email': 'photouser@gmail.com', 'gender': 'M', 'phone_number': '9876543210', 'profile_photo-clear': 'on'},
            files={},
            instance=u2
        )
        self.assertTrue(form3.is_valid(), form3.errors)
        u3 = form3.save()
        self.assertFalse(bool(u3.profile_photo))
        # Second photo must now also be deleted from disk
        self.assertFalse(default_storage.exists(second_photo))

    def test_phone_number_uniqueness_on_registration_and_update(self):
        from users.forms import UserRegisterForm, UserUpdateForm
        User.objects.create_user(
            username="existing_phone_user",
            email="existing_phone@test.com",
            password="TestPassword123!",
            phone_number="9876543299",
            is_approved=True
        )

        # 1. Registration with duplicate phone
        reg_form = UserRegisterForm(data={
            'username': 'new_candidate',
            'full_name': 'New Candidate',
            'email': 'new_candidate@test.com',
            'phone_number': '9876543299',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
            'gender': 'M',
            'profile_for': 'Self',
            'community': 'hindu',
            'religion': 'Hindu',
            'mother_tongue': 'Hindi',
        })
        self.assertFalse(reg_form.is_valid())
        self.assertIn("phone_number", reg_form.errors)

        # 2. Update profile with duplicate phone
        other_user = User.objects.create_user(
            username="other_candidate",
            email="other_candidate@test.com",
            password="TestPassword123!",
            phone_number="9876543288",
            is_approved=True
        )
        update_form = UserUpdateForm(
            data={
                'full_name': 'Other Candidate',
                'email': 'other_candidate@test.com',
                'gender': 'M',
                'phone_number': '9876543299'
            },
            instance=other_user
        )
        self.assertFalse(update_form.is_valid())
        self.assertIn("phone_number", update_form.errors)

    def test_email_verification_token_mismatched_email_rejected(self):
        from core.services import send_verification_email
        from django.core.signing import TimestampSigner

        test_user = User.objects.create_user(
            username="token_binding_user",
            email="original@example.com",
            password="TestPassword123!",
            is_approved=True,
            is_email_verified=False
        )

        signer = TimestampSigner()
        # Token generated for original email
        token = signer.sign(f"{test_user.id}:{test_user.email.strip().lower()}")

        # User's email changes before token is clicked
        test_user.email = "changed@example.com"
        test_user.save()

        # Visiting verification link with stale token must reject verification
        res = self.client.get(reverse('verify_email', args=[token]))
        self.assertEqual(res.status_code, 302)
        test_user.refresh_from_db()
        self.assertFalse(test_user.is_email_verified)

    def test_resend_verification_open_redirect_prevented(self):
        active_user = User.objects.create_user(
            username="redirect_test_user",
            email="redirect_user@example.com",
            password="TestPassword123!",
            is_approved=True,
            is_email_verified=False
        )
        self.client.login(username="redirect_test_user", password="TestPassword123!")

        # Insecure substring attempt: evil.com/?x=testserver
        response = self.client.get(
            reverse('resend_verification'),
            HTTP_REFERER="https://attacker-evil.com/phish?x=testserver"
        )
        self.assertEqual(response.status_code, 302)
        # Must redirect safely to local view, never to external attacker site
        self.assertFalse(response['Location'].startswith("https://attacker-evil.com"))

    def test_matchmaking_city_filter_invalid_type_does_not_500(self):
        active_user = User.objects.create_user(
            username="filter_safety_user",
            email="filtersafety@example.com",
            password="TestPassword123!",
            is_approved=True,
            is_email_verified=True,
            gender='M'
        )
        self.client.login(username="filter_safety_user", password="TestPassword123!")

        # String city ID
        res1 = self.client.get(reverse('profile_list'), {'city': 'abc'})
        self.assertEqual(res1.status_code, 200)

        # Float city ID
        res2 = self.client.get(reverse('profile_list'), {'city': '1.5'})
        self.assertEqual(res2.status_code, 200)

    def test_matchmaking_age_filter_bounds_inclusive(self):
        from datetime import date
        today = date.today()
        # Exactly 30 years old today
        dob_30 = date(today.year - 30, today.month, today.day)
        # Exactly 31 years old today
        dob_31 = date(today.year - 31, today.month, today.day)

        p30 = User.objects.create_user(
            username="candidate_30",
            email="candidate30@example.com",
            password="TestPassword123!",
            full_name="Candidate 30",
            gender='F',
            date_of_birth=dob_30,
            is_approved=True,
            is_email_verified=True,
        )
        p31 = User.objects.create_user(
            username="candidate_31",
            email="candidate31@example.com",
            password="TestPassword123!",
            full_name="Candidate 31",
            gender='F',
            date_of_birth=dob_31,
            is_approved=True,
            is_email_verified=True,
        )

        viewer = User.objects.create_user(
            username="age_filter_viewer",
            email="ageviewer@example.com",
            password="TestPassword123!",
            gender='M',
            is_approved=True,
            is_email_verified=True
        )
        self.client.login(username="age_filter_viewer", password="TestPassword123!")

        # Query max_age=30: candidate_30 must be included, candidate_31 must be excluded
        res = self.client.get(reverse('profile_list'), {'max_age': '30', 'gender': 'F'})
        self.assertEqual(res.status_code, 200)
        names = [p.full_name for p in res.context['page_obj']]
        self.assertIn("Candidate 30", names)
        self.assertNotIn("Candidate 31", names)

    def test_phone_number_rejects_non_ascii_digits(self):
        from users.forms import UserRegisterForm, UserUpdateForm
        # Registration with unicode superscripts
        reg_form = UserRegisterForm(data={
            'username': 'unicode_candidate',
            'full_name': 'Unicode Candidate',
            'email': 'unicode@test.com',
            'phone_number': '9\u00B2\u00B2\u00B2\u00B2\u00B2\u00B2\u00B2\u00B2\u00B2',  # 9²²²²²²²²²
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
            'gender': 'M',
            'profile_for': 'Self',
            'community': 'hindu',
            'religion': 'Hindu',
            'mother_tongue': 'Hindi',
        })
        self.assertFalse(reg_form.is_valid())
        self.assertIn("phone_number", reg_form.errors)

        # Profile update with non-ASCII digits
        u = User.objects.create_user(
            username="update_non_ascii_user",
            email="updnonascii@test.com",
            password="StrongPassword123!",
            phone_number="9876543201",
            is_approved=True
        )
        update_form = UserUpdateForm(
            data={
                'full_name': 'Update Candidate',
                'email': 'updnonascii@test.com',
                'gender': 'M',
                'phone_number': '9\u00B2\u00B2\u00B2\u00B2\u00B2\u00B2\u00B2\u00B2\u00B2'
            },
            instance=u
        )
        self.assertFalse(update_form.is_valid())
        self.assertIn("phone_number", update_form.errors)

    def test_login_rate_limiting_locks_account_after_5_failures(self):
        from django.core.cache import cache
        test_login_user = User.objects.create_user(
            username="lockout_victim",
            email="lockout@example.com",
            password="RealPassword123!",
            is_approved=True,
            is_email_verified=True
        )

        # Clean cache keys before test
        cache.clear()

        # 5 failed attempts with wrong password from default IP (127.0.0.1)
        for _ in range(5):
            res = self.client.post(reverse('login'), {
                'username': 'lockout_victim',
                'password': 'WrongPassword123!'
            })
            self.assertEqual(res.status_code, 200)

        # 6th attempt with REAL password from the SAME IP must be blocked because that IP is locked
        res_locked = self.client.post(reverse('login'), {
            'username': 'lockout_victim',
            'password': 'RealPassword123!'
        })
        self.assertEqual(res_locked.status_code, 200)
        self.assertContains(res_locked, "temporarily locked")

        # 7th attempt with REAL password from a DIFFERENT IP (e.g. legitimate user's device) MUST succeed
        legit_res = self.client.post(reverse('login'), {
            'username': 'lockout_victim',
            'password': 'RealPassword123!'
        }, REMOTE_ADDR='198.51.100.77')
        self.assertRedirects(legit_res, reverse('home'))

        # Cleanup
        cache.clear()

    def test_get_client_ip_ignores_spoofed_headers(self):
        from core.utils import get_client_ip
        from django.test import RequestFactory

        rf = RequestFactory()

        # Direct client sends fake CF-Connecting-IP and fake X-Forwarded-For
        req = rf.post('/contact/', HTTP_CF_CONNECTING_IP='8.8.8.8', HTTP_X_FORWARDED_FOR='1.2.3.4')
        self.assertEqual(get_client_ip(req), '127.0.0.1')

        # Behind Nginx with authenticated X-Real-IP
        req_nginx = rf.post('/contact/', HTTP_X_REAL_IP='203.0.113.195', HTTP_CF_CONNECTING_IP='8.8.8.8')
        self.assertEqual(get_client_ip(req_nginx), '203.0.113.195')


    def test_delete_account_requires_correct_password(self):
        del_user = User.objects.create_user(
            username="account_to_delete",
            email="delete_me@example.com",
            password="SecretPassword123!",
            is_approved=True,
            is_email_verified=True
        )
        self.client.login(username="account_to_delete", password="SecretPassword123!")

        # 1. POST without password fails
        res_no_pwd = self.client.post(reverse('delete_account'), {})
        self.assertEqual(res_no_pwd.status_code, 200)
        self.assertTrue(User.objects.filter(username="account_to_delete").exists())

        # 2. POST with wrong password fails
        res_wrong_pwd = self.client.post(reverse('delete_account'), {'password': 'WrongPassword!'})
        self.assertEqual(res_wrong_pwd.status_code, 200)
        self.assertTrue(User.objects.filter(username="account_to_delete").exists())

        # 3. POST with correct password succeeds
        res_correct = self.client.post(reverse('delete_account'), {'password': 'SecretPassword123!'})
        self.assertEqual(res_correct.status_code, 302)
        self.assertFalse(User.objects.filter(username="account_to_delete").exists())

    def test_payment_order_preserved_when_user_deleted(self):
        from payments.models import Plan, PaymentOrder
        pay_user = User.objects.create_user(
            username="payment_audit_user",
            email="audit@example.com",
            password="Password123!",
            is_approved=True,
            is_email_verified=True
        )
        plan, _ = Plan.objects.get_or_create(
            code="gold",
            defaults={'name': 'Gold Plan', 'price': 399.00, 'duration_days': 90}
        )
        order = PaymentOrder.objects.create(
            user=pay_user,
            plan=plan,
            amount=399.00,
            utr_number="UTR123456789",
            status="completed"
        )

        order_id = order.id
        # Delete user
        pay_user.delete()

        # Payment order must survive deletion with user set to null
        order.refresh_from_db()
        self.assertIsNone(order.user)
        self.assertEqual(order.amount, 399.00)
        self.assertEqual(order.utr_number, "UTR123456789")


