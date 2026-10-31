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

        # 1. Registered member submission goes through immediately (200 OK)
        user = User.objects.create_user(
            username="contact_member",
            email="member@example.com",
            password="TestPass123!",
            is_approved=True,
            is_email_verified=True
        )
        self.client.login(username="contact_member", password="TestPass123!")
        response = self.client.post(reverse('contact_us'), {
            'name': 'Member Submitter',
            'email': 'member@example.com',
            'message': 'Testing member contact submission',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your message has been sent successfully")
        self.client.logout()

        # 2. Guest submission redirects to OTP verification
        guest_post = self.client.post(reverse('contact_us'), {
            'name': 'Guest Submitter',
            'email': 'guest@example.com',
            'message': 'Testing guest inquiry with OTP',
        })
        self.assertRedirects(guest_post, reverse('contact_verify'))

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

        member = User.objects.create_user(
            username="rate_contact_member",
            email="ratemember@example.com",
            password="TestPass123!",
            is_approved=True
        )
        self.client.login(username="rate_contact_member", password="TestPass123!")
        ip_env = {'REMOTE_ADDR': '198.51.100.42'}

        for i in range(3):
            response = self.client.post(reverse('contact_us'), {
                'name': f'Submitter {i}',
                'email': f'submitter{i}@example.com',
                'message': f'Message {i}',
            }, **ip_env)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Your message has been sent successfully")

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


class Phase3SecurityAndModerationTests(TestCase):
    def setUp(self):
        self.approved_user = User.objects.create_user(
            username="approved_mod_user",
            email="mod_user@example.com",
            password="ModPassword123!",
            full_name="Original Name",
            gender="M",
            phone_number="9876543210",
            is_approved=True,
            is_email_verified=True,
            is_suspended=False,
        )
        self.suspended_user = User.objects.create_user(
            username="suspended_user",
            email="suspended@example.com",
            password="ModPassword123!",
            full_name="Suspended User",
            gender="M",
            phone_number="9876543211",
            is_approved=True,
            is_email_verified=True,
            is_suspended=True,
        )
        self.unapproved_user = User.objects.create_user(
            username="unapproved_user",
            email="unapproved@example.com",
            password="ModPassword123!",
            full_name="Unapproved User",
            gender="F",
            phone_number="9876543212",
            is_approved=False,
            is_email_verified=True,
            is_suspended=False,
        )

    def test_suspended_user_blocked_from_edit_profile(self):
        self.client.login(username="suspended_user", password="ModPassword123!")
        res = self.client.get(reverse('edit_profile'))
        self.assertEqual(res.status_code, 302)
        res_post = self.client.post(reverse('edit_profile'), {'bio': 'Hacked bio'})
        self.assertEqual(res_post.status_code, 302)

    def test_unapproved_user_allowed_access_to_edit_profile(self):
        self.client.login(username="unapproved_user", password="ModPassword123!")
        res = self.client.get(reverse('edit_profile'))
        self.assertEqual(res.status_code, 200)

    def test_profile_update_preserves_approval_and_flags_needs_review(self):
        self.client.login(username="approved_mod_user", password="ModPassword123!")
        res = self.client.post(reverse('edit_profile'), {
            'full_name': 'Changed Full Name',
            'email': 'mod_user@example.com',
            'gender': 'M',
            'phone_number': '9876543210',
            'bio': 'Original bio',
        })
        self.assertEqual(res.status_code, 302)
        self.approved_user.refresh_from_db()
        self.assertEqual(self.approved_user.full_name, 'Changed Full Name')
        self.assertTrue(self.approved_user.is_approved)
        self.assertTrue(self.approved_user.needs_review)

    def test_non_critical_bio_change_preserves_approval_and_flags_needs_review(self):
        self.client.login(username="approved_mod_user", password="ModPassword123!")
        res = self.client.post(reverse('edit_profile'), {
            'full_name': 'Original Name',
            'email': 'mod_user@example.com',
            'gender': 'M',
            'phone_number': '9876543210',
            'bio': 'Updated bio only',
        })
        self.assertEqual(res.status_code, 302)
        self.approved_user.refresh_from_db()
        self.assertTrue(self.approved_user.is_approved)
        self.assertTrue(self.approved_user.needs_review)

    def test_image_decompression_bomb_pixel_cap(self):
        from users.validators import validate_image_file
        from django.core.exceptions import ValidationError
        from PIL import Image
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Create an image with > 16 million pixels (5000 x 4000 = 20,000,000 pixels)
        buf = BytesIO()
        img = Image.new('RGB', (5000, 4000), color='blue')
        img.save(buf, format='JPEG')
        buf.seek(0)
        upload = SimpleUploadedFile("bomb.jpg", buf.read(), content_type="image/jpeg")

        with self.assertRaises(ValidationError) as ctx:
            validate_image_file(upload)
        self.assertIn("resolution is too large", str(ctx.exception).lower())


class Phase4VisibilityAndPrivacyTests(TestCase):
    def setUp(self):
        from datetime import date
        self.member_male = User.objects.create_user(
            username="member_m",
            email="member_m@example.com",
            password="Password123!",
            full_name="Male Member",
            gender="M",
            phone_number="9876543201",
            date_of_birth=date(1995, 5, 15),
            father_name="Father Male",
            mother_name="Mother Male",
            address="123 Civil Lines, Varanasi",
            is_approved=True,
            is_email_verified=True,
            is_suspended=False,
        )
        self.member_female = User.objects.create_user(
            username="member_f",
            email="member_f@example.com",
            password="Password123!",
            full_name="Female Member",
            gender="F",
            phone_number="9876543202",
            date_of_birth=date(1998, 8, 20),
            father_name="Father Female",
            mother_name="Mother Female",
            address="456 Cantt Road, Lucknow",
            is_approved=True,
            is_email_verified=True,
            is_suspended=False,
        )
        self.admin_user = User.objects.create_superuser(
            username="admin_p4",
            email="admin_p4@example.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=True,
        )
        self.suspended_target = User.objects.create_user(
            username="suspended_target_p4",
            email="susp_target_p4@example.com",
            password="Password123!",
            full_name="Suspended Person",
            gender="F",
            is_approved=True,
            is_email_verified=True,
            is_suspended=True,
        )
        self.unapproved_target = User.objects.create_user(
            username="unapproved_target_p4",
            email="unapproved_p4@example.com",
            password="Password123!",
            full_name="Unapproved Person",
            gender="F",
            is_approved=False,
            is_email_verified=True,
            is_suspended=False,
        )

    def test_visibility_service_visible_profiles_filtering(self):
        from users.visibility import visible_profiles
        from communications.models import Block

        # Female member is visible to male member
        qs_m = visible_profiles(self.member_male)
        self.assertIn(self.member_female, qs_m)
        self.assertNotIn(self.member_male, qs_m)
        self.assertNotIn(self.admin_user, qs_m)
        self.assertNotIn(self.suspended_target, qs_m)
        self.assertNotIn(self.unapproved_target, qs_m)

        # When blocked, female member is excluded
        Block.objects.create(blocker=self.member_male, blocked=self.member_female)
        qs_blocked = visible_profiles(self.member_male)
        self.assertNotIn(self.member_female, qs_blocked)

        # Also excluded if female member blocked male member
        Block.objects.all().delete()
        Block.objects.create(blocker=self.member_female, blocked=self.member_male)
        qs_blocked2 = visible_profiles(self.member_male)
        self.assertNotIn(self.member_female, qs_blocked2)

        # Blocked profiles must also be excluded for admin viewers
        Block.objects.all().delete()
        qs_admin_before = visible_profiles(self.admin_user)
        self.assertIn(self.member_female, qs_admin_before)
        Block.objects.create(blocker=self.admin_user, blocked=self.member_female)
        qs_admin_after = visible_profiles(self.admin_user)
        self.assertNotIn(self.member_female, qs_admin_after)

    def test_admin_matchmaking_feed_excludes_blocked_users(self):
        from django.urls import reverse
        from communications.models import Block

        self.client.login(username="admin_p4", password="AdminPassword123!")
        res = self.client.get(reverse('profile_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, self.member_female.full_name)

        # Admin blocks the member
        Block.objects.create(blocker=self.admin_user, blocked=self.member_female)
        res_after = self.client.get(reverse('profile_list'))
        self.assertEqual(res_after.status_code, 200)
        self.assertNotContains(res_after, self.member_female.full_name)

    def test_view_profile_shows_unblock_option_when_blocked_by_viewer(self):
        from django.urls import reverse
        from communications.models import Block

        self.client.login(username="admin_p4", password="AdminPassword123!")
        # Before block, shows Block option
        res = self.client.get(reverse('view_profile', args=[self.member_female.id]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Block")
        self.assertNotContains(res, "Unblock")

        # After block, shows Unblock option
        Block.objects.create(blocker=self.admin_user, blocked=self.member_female)
        res_blocked = self.client.get(reverse('view_profile', args=[self.member_female.id]))
        self.assertEqual(res_blocked.status_code, 200)
        self.assertContains(res_blocked, "Unblock")
        self.assertNotContains(res_blocked, 'action="/interests/block/')

    def test_visibility_service_can_view(self):
        from users.visibility import can_view
        from communications.models import Block

        # Normal view of approved member
        self.assertTrue(can_view(self.member_male, self.member_female))
        self.assertTrue(can_view(self.member_male, self.member_male))

        # Cannot view staff account
        self.assertFalse(can_view(self.member_male, self.admin_user))

        # Cannot view suspended or unapproved account
        self.assertFalse(can_view(self.member_male, self.suspended_target))
        self.assertFalse(can_view(self.member_male, self.unapproved_target))

        # Admin can view anyone (for moderation)
        self.assertTrue(can_view(self.admin_user, self.suspended_target))
        self.assertTrue(can_view(self.admin_user, self.unapproved_target))

        # Blocked accounts cannot view each other
        Block.objects.create(blocker=self.member_male, blocked=self.member_female)
        self.assertFalse(can_view(self.member_male, self.member_female))
        self.assertFalse(can_view(self.member_female, self.member_male))

    def test_unmatched_user_cannot_see_parental_names_exact_dob_or_contact(self):
        from django.urls import reverse
        self.client.login(username="member_m", password="Password123!")
        res = self.client.get(reverse('view_profile', args=[self.member_female.id]))
        self.assertEqual(res.status_code, 200)

        # Contact details must be hidden
        self.assertNotContains(res, "9876543202")
        self.assertNotContains(res, "member_f@example.com")
        self.assertNotContains(res, "456 Cantt Road")

        # Parental names must be hidden
        self.assertNotContains(res, "Father Female")
        self.assertNotContains(res, "Mother Female")
        self.assertContains(res, "Visible upon mutual match")

        # Exact DOB must be hidden; only age should show
        self.assertNotContains(res, "Aug. 20, 1998")
        self.assertNotContains(res, "1998-08-20")
        self.assertContains(res, f"{self.member_female.age} yrs old")

    def test_matched_user_sees_parental_names_exact_dob_and_contact(self):
        from django.urls import reverse
        from communications.models import ContactRequest

        # Create accepted mutual match
        ContactRequest.objects.create(
            sender=self.member_male,
            receiver=self.member_female,
            status="accepted"
        )

        self.client.login(username="member_m", password="Password123!")
        res = self.client.get(reverse('view_profile', args=[self.member_female.id]))
        self.assertEqual(res.status_code, 200)

        # Contact details visible
        self.assertContains(res, "9876543202")
        self.assertContains(res, "member_f@example.com")
        self.assertContains(res, "456 Cantt Road")

        # Parental names visible
        self.assertContains(res, "Father Female")
        self.assertContains(res, "Mother Female")

        # Exact DOB visible
        self.assertContains(res, "Aug. 20, 1998")

    def test_admin_viewer_dropdown_links_to_secure_admin_panel(self):
        from django.urls import reverse
        self.client.login(username="admin_p4", password="AdminPassword123!")
        res = self.client.get(reverse('view_profile', args=[self.member_female.id]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f"/secure-admin-panel/users/customuser/{self.member_female.id}/change/")
        self.assertNotContains(res, f"/admin/users/customuser/{self.member_female.id}/change/")


class Phase5LockoutAndRateLimitingTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(
            username="victim_p5",
            email="victim_p5@example.com",
            password="StrongPassword123!",
            is_approved=True,
            is_email_verified=True,
        )

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_ip_network_key_helper(self):
        from core.utils import get_ip_network_key
        # IPv4 unchanged
        self.assertEqual(get_ip_network_key("203.0.113.195"), "203.0.113.195")
        self.assertEqual(get_ip_network_key("127.0.0.1"), "127.0.0.1")

        # IPv6 normalized to /64 subnet prefix
        ip1 = "2001:db8:abcd:0012:0000:0000:0000:0001"
        ip2 = "2001:db8:abcd:0012:ffff:ffff:ffff:ffff"
        diff_subnet = "2001:db8:abcd:0099::1"

        self.assertEqual(get_ip_network_key(ip1), "2001:db8:abcd:12::/64")
        self.assertEqual(get_ip_network_key(ip2), "2001:db8:abcd:12::/64")
        self.assertEqual(get_ip_network_key(ip1), get_ip_network_key(ip2))
        self.assertNotEqual(get_ip_network_key(ip1), get_ip_network_key(diff_subnet))

    def test_ipv6_64_subnet_login_lockout(self):
        # 5 failed attempts rotating through different IPs within the same /64
        for i in range(1, 6):
            res = self.client.post(
                reverse('login'),
                {'username': 'victim_p5', 'password': 'WrongPassword123!'},
                REMOTE_ADDR=f"2001:db8:abcd:12::{i}"
            )
            self.assertEqual(res.status_code, 200)

        # 6th attempt from a brand-new IP in that same /64 must be locked
        res_locked = self.client.post(
            reverse('login'),
            {'username': 'victim_p5', 'password': 'StrongPassword123!'},
            REMOTE_ADDR="2001:db8:abcd:12::dead:beef"
        )
        self.assertEqual(res_locked.status_code, 200)
        self.assertContains(res_locked, "temporarily locked")

        # Attempt from a DIFFERENT /64 subnet must succeed
        res_allowed = self.client.post(
            reverse('login'),
            {'username': 'victim_p5', 'password': 'StrongPassword123!'},
            REMOTE_ADDR="2001:db8:abcd:99::1"
        )
        self.assertRedirects(res_allowed, reverse('home'))

    def test_ip_wide_limit_raised_above_20_failures(self):
        # 25 failed attempts with different usernames from the SAME shared carrier IP (e.g. 198.51.100.5)
        for i in range(25):
            res = self.client.post(
                reverse('login'),
                {'username': f'random_user_{i}', 'password': 'WrongPassword123!'},
                REMOTE_ADDR='198.51.100.5'
            )
            self.assertEqual(res.status_code, 200)

        # 26th attempt for our legitimate user with correct credentials from that SAME IP must NOT be locked out
        res_legit = self.client.post(
            reverse('login'),
            {'username': 'victim_p5', 'password': 'StrongPassword123!'},
            REMOTE_ADDR='198.51.100.5'
        )
        self.assertRedirects(res_legit, reverse('home'))

    def test_account_level_attack_alert_without_denial_of_service(self):
        from django.core.cache import cache
        # Simulate distributed attack: 50 failed attempts across 50 different IPs
        for i in range(1, 51):
            ip = f"198.51.{i // 256}.{i % 256 + 1}"
            self.client.post(
                reverse('login'),
                {'username': 'victim_p5', 'password': 'WrongPassword123!'},
                REMOTE_ADDR=ip
            )

        # Verify account-level counter reached 50
        self.assertGreaterEqual(cache.get("login_account_attempts_victim_p5", 0), 50)
        self.assertTrue(cache.get("account_security_alert_victim_p5"))

        # Legitimate user logs in with CORRECT password from their home IP -> MUST SUCCEED (No DoS)
        res_success = self.client.post(
            reverse('login'),
            {'username': 'victim_p5', 'password': 'StrongPassword123!'},
            REMOTE_ADDR='203.0.113.88',
            follow=True
        )
        self.assertEqual(res_success.status_code, 200)
        # Security notice message displayed to user
        self.assertContains(res_success, "Security Notice")
        # Counter and alert flag reset after successful legitimate login
        self.assertIsNone(cache.get("account_security_alert_victim_p5"))
        self.assertIsNone(cache.get("login_account_attempts_victim_p5"))

    def test_contact_form_ipv6_64_subnet_rate_limiting(self):
        # 3 submissions from 3 different IPs in the same /64
        for i in range(1, 4):
            res = self.client.post(
                reverse('contact_us'),
                {
                    'name': f'Submitter {i}',
                    'email': f'submitter{i}@example.com',
                    'message': f'Message {i}',
                },
                REMOTE_ADDR=f"2001:db8:beef:42::{i}"
            )
            self.assertIn(res.status_code, [200, 302])

        # 4th submission from another IP in that same /64 must be rate-limited
        res_blocked = self.client.post(
            reverse('contact_us'),
            {
                'name': 'Submitter 4',
                'email': 'submitter4@example.com',
                'message': 'Message 4',
            },
            REMOTE_ADDR="2001:db8:beef:42::feed:beef"
        )
        self.assertEqual(res_blocked.status_code, 200)
        self.assertContains(res_blocked, "Too many messages sent from your IP")


class Phase6EdgeCasesAndSRITests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        from datetime import date
        from users.models import City, Caste
        cache.clear()
        self.user = User.objects.create_user(
            username="p6_user",
            email="p6_user@example.com",
            password="P6Password123!",
            is_active=True,
            is_approved=True,
            is_email_verified=True,
            gender="M",
            phone_number="9876543299",
            date_of_birth=date(1995, 5, 20),
            height_cm=175,
            city=City.objects.create(name="P6City"),
            caste_community=Caste.objects.create(name="P6Caste"),
        )
        self.other_user = User.objects.create_user(
            username="p6_other",
            email="p6_other@example.com",
            password="P6Password123!",
            is_active=True,
            is_approved=True,
            is_email_verified=True,
            gender="F",
            phone_number="9876543298",
            date_of_birth=date(1996, 6, 21),
            height_cm=165,
            city=City.objects.get(name="P6City"),
            caste_community=Caste.objects.get(name="P6Caste"),
        )

    def test_search_age_overflow_and_out_of_range(self):
        self.client.login(username="p6_user", password="P6Password123!")
        huge_age = "999999999999999999999999999999"
        res_min = self.client.get(reverse('profile_list'), {'min_age': huge_age})
        self.assertEqual(res_min.status_code, 200)

        res_max = self.client.get(reverse('profile_list'), {'max_age': huge_age})
        self.assertEqual(res_max.status_code, 200)

        res_neg = self.client.get(reverse('profile_list'), {'min_age': '-50'})
        self.assertEqual(res_neg.status_code, 200)

    def test_update_request_invalid_action_returns_404(self):
        from communications.models import ContactRequest
        self.client.login(username="p6_user", password="P6Password123!")
        req = ContactRequest.objects.create(
            sender=self.other_user,
            receiver=self.user,
            status="pending"
        )
        res = self.client.post(
            reverse('update_request', kwargs={'request_id': req.id, 'action': 'invalid_action'})
        )
        self.assertEqual(res.status_code, 404)
        req.refresh_from_db()
        self.assertEqual(req.status, "pending")

    def test_subresource_integrity_attributes_present(self):
        res = self.client.get(reverse('home'))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        # Verify Bootstrap CSS SRI
        self.assertIn('cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css', content)
        self.assertIn('integrity="sha384-T3c6CoIi6uLrA9TneNEoa7RxnatzjcDSCmG1MXxSR1GAsXEV/Dwwykc2MPK8M2HN"', content)

        # Verify HTMX SRI
        self.assertIn('cdn.jsdelivr.net/npm/htmx.org@1.9.12/dist/htmx.min.js', content)
        self.assertIn('integrity="sha384-ujb1lZYygJmzgSwoxRggbCHcjc0rB2XoQrxeTUQyRjrOnlCoYta87iKBWq3EsdM2"', content)

        # Verify Bootstrap Bundle JS SRI
        self.assertIn('cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js', content)
        self.assertIn('integrity="sha384-C6RzsynM9kWDrMNeT87bh95OGNyZPhcTNXj1NW7RuBCsyN/o0jlpcV8Qyq46cDfL"', content)

        # All 3 must specify crossorigin="anonymous"
        self.assertGreaterEqual(content.count('crossorigin="anonymous"'), 3)


class Phase7PaymentCapsAndDBConstraintsTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        from datetime import date
        from users.models import City, Caste
        from payments.models import Plan
        cache.clear()

        self.city = City.objects.create(name="P7City")
        self.caste = Caste.objects.create(name="P7Caste")

        self.user = User.objects.create_user(
            username="p7_user",
            email="p7_user@example.com",
            password="P7Password123!",
            is_active=True,
            is_approved=True,
            is_email_verified=True,
            gender="M",
            phone_number="9876543111",
            date_of_birth=date(1994, 4, 15),
            height_cm=178,
            city=self.city,
            caste_community=self.caste,
        )

        self.plan = Plan.objects.create(
            code='silver_p7',
            name='Silver P7',
            price=199.00,
            duration_days=30,
            features='Feature 1\nFeature 2',
            is_active=True,
        )

    def test_pending_payment_order_cap(self):
        from payments.models import PaymentOrder
        self.client.login(username="p7_user", password="P7Password123!")

        # Create 3 pending orders
        for i in range(3):
            PaymentOrder.objects.create(
                user=self.user,
                plan=self.plan,
                amount=self.plan.price,
                utr_number=f"11112222333{i}",
                status='pending'
            )

        # GET checkout should redirect to payment_history with warning
        res_get = self.client.get(reverse('checkout', kwargs={'plan_code': self.plan.code}))
        self.assertEqual(res_get.status_code, 302)
        self.assertIn(reverse('payment_history'), res_get.url)

        # POST checkout should also reject and redirect to payment_history
        res_post = self.client.post(
            reverse('checkout', kwargs={'plan_code': self.plan.code}),
            {'utr_number': '999988887777'}
        )
        self.assertEqual(res_post.status_code, 302)
        self.assertIn(reverse('payment_history'), res_post.url)
        self.assertEqual(PaymentOrder.objects.filter(user=self.user, status='pending').count(), 3)

    def test_database_unique_constraint_email(self):
        from django.db import IntegrityError
        from datetime import date
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="p7_duplicate_email",
                email="P7_USER@EXAMPLE.COM",  # Case variation of p7_user@example.com
                password="P7Password123!",
                phone_number="9876543222",
                gender="F",
                date_of_birth=date(1995, 1, 1),
            )

    def test_database_unique_constraint_phone(self):
        from django.db import IntegrityError
        from datetime import date
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="p7_duplicate_phone",
                email="different_email@example.com",
                password="P7Password123!",
                phone_number="9876543111",  # Same as self.user.phone_number
                gender="F",
                date_of_birth=date(1995, 1, 1),
            )

    def test_profile_save_generic_error_and_no_leak(self):
        from unittest.mock import patch
        self.client.login(username="p7_user", password="P7Password123!")

        with patch('users.forms.UserUpdateForm.save', side_effect=RuntimeError("Secret internal database server timeout on 192.168.1.55")):
            res = self.client.post(
                reverse('edit_profile'),
                {
                    'full_name': 'New Name',
                    'email': 'p7_user@example.com',
                    'gender': 'M',
                    'phone_number': '9876543111',
                    'bio': 'Updated bio',
                },
                follow=True
            )
            content = res.content.decode('utf-8')
            # Must NOT leak the internal database error
            self.assertNotIn("Secret internal database server timeout", content)
            self.assertNotIn("192.168.1.55", content)
            # Must display safe generic error
            self.assertIn("An error occurred while saving your profile", content)

    def test_profile_view_rate_limiting(self):
        from datetime import date
        other_user = User.objects.create_user(
            username="p7_target",
            email="p7_target@example.com",
            password="P7Password123!",
            is_active=True,
            is_approved=True,
            is_email_verified=True,
            gender="F",
            phone_number="9876543333",
            date_of_birth=date(1996, 6, 21),
            height_cm=165,
            city=self.city,
            caste_community=self.caste,
        )

        self.client.login(username="p7_user", password="P7Password123!")

        from django.core.cache import cache
        rate_key = f"profile_view_rate_{self.user.id}"
        cache.set(rate_key, 120, timeout=3600)

        # 121st view should be blocked
        res = self.client.get(reverse('view_profile', kwargs={'user_id': other_user.id}))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse('profile_list'), res.url)

        # Staff user should be exempt
        self.user.is_staff = True
        self.user.save()
        res_staff = self.client.get(reverse('view_profile', kwargs={'user_id': other_user.id}))
        self.assertEqual(res_staff.status_code, 200)
        cache.delete(rate_key)



class RegistrationWizardAndEducationTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        from users.models import City
        self.city = City.objects.create(name="Varanasi")

    def test_customuser_education_field_saved(self):
        user = User.objects.create_user(
            username="eduuser",
            password="StrongPass123!",
            education="B.Tech Computer Science"
        )
        self.assertEqual(user.education, "B.Tech Computer Science")
        user.refresh_from_db()
        self.assertEqual(user.education, "B.Tech Computer Science")

    def test_user_register_form_with_education_and_step2_fields(self):
        from users.forms import UserRegisterForm
        form_data = {
            'username': 'wizarduser',
            'full_name': 'Wizard User',
            'gender': 'M',
            'date_of_birth': '1996-04-12',
            'phone_number': '9876543211',
            'email': 'wizard@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'education': 'MBA Finance',
            'occupation': 'Financial Analyst',
            'city': self.city.id,
            'height_cm': 175,
            'caste': 'Brahmin',
            'sub_caste': 'Shukla',
            'bio': 'Passionate finance professional looking for a life partner.',
        }
        form = UserRegisterForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.education, 'MBA Finance')
        self.assertEqual(user.occupation, 'Financial Analyst')
        self.assertEqual(user.city, self.city)
        self.assertEqual(user.height_cm, 175)
        self.assertEqual(user.caste, 'Brahmin')
        self.assertEqual(user.sub_caste, 'Shukla')
        self.assertEqual(user.bio, 'Passionate finance professional looking for a life partner.')

    def test_user_update_form_with_education(self):
        from datetime import date
        from users.forms import UserUpdateForm
        user = User.objects.create_user(
            username="updateedu",
            password="StrongPass123!",
            phone_number="9876543212",
            date_of_birth=date(1994, 2, 10),
            full_name="Update User",
        )
        form_data = {
            'full_name': 'Update User',
            'email': 'updateedu@example.com',
            'gender': 'M',
            'phone_number': '9876543212',
            'date_of_birth': '1994-02-10',
            'education': 'MBBS Doctor',
            'occupation': 'Physician',
            'city': self.city.id,
            'height_cm': 180,
            'caste': 'Rajput',
            'sub_caste': 'Singh',
            'bio': 'Doctor based in Varanasi.',
        }
        form = UserUpdateForm(data=form_data, instance=user)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.education, 'MBBS Doctor')
        self.assertEqual(saved.occupation, 'Physician')

    def test_registration_view_get_renders_wizard_structure(self):
        res = self.client.get(reverse('register'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="step1Container"')
        self.assertContains(res, 'id="step2Container"')
        self.assertContains(res, 'enctype="multipart/form-data"')
        self.assertContains(res, 'Education / Degree')
        self.assertContains(res, 'Step 1: Account &amp; Identity')
        self.assertContains(res, 'Step 2: Matrimonial Details')

    def test_registration_view_post_creates_user_with_education(self):
        post_data = {
            'username': 'registerednew',
            'full_name': 'New User',
            'gender': 'F',
            'date_of_birth': '1997-08-20',
            'phone_number': '9876543213',
            'email': 'newuser@example.com',
            'password1': 'SecretPass123!',
            'password2': 'SecretPass123!',
            'education': 'M.Tech CSE',
            'occupation': 'Software Engineer',
            'city': self.city.id,
            'height_cm': 165,
            'caste': 'Kayastha',
            'sub_caste': 'Srivastava',
            'bio': 'Software Engineer in tech company.',
        }
        res = self.client.post(reverse('register'), data=post_data, follow=True)
        self.assertEqual(res.status_code, 200)
        created_user = User.objects.get(username='registerednew')
        self.assertEqual(created_user.education, 'M.Tech CSE')
        self.assertEqual(created_user.occupation, 'Software Engineer')
        self.assertEqual(created_user.city, self.city)

    def test_my_profile_and_view_profile_display_education(self):
        user_a = User.objects.create_user(
            username="usera",
            password="StrongPass123!",
            phone_number="9876543214",
            full_name="User Alpha",
            education="PhD Mathematics",
            occupation="Professor",
            gender="M",
            is_approved=True,
            is_email_verified=True,
        )
        user_b = User.objects.create_user(
            username="userb",
            password="StrongPass123!",
            phone_number="9876543215",
            full_name="User Beta",
            education="M.Com Gold Medalist",
            occupation="Chartered Accountant",
            gender="F",
            is_approved=True,
            is_email_verified=True,
        )
        self.client.force_login(user_a)

        # Check user_a viewing their own profile
        res_my = self.client.get(reverse('my_profile'))
        self.assertEqual(res_my.status_code, 200)
        self.assertContains(res_my, "PhD Mathematics")

        # Check user_a viewing user_b's profile
        res_view = self.client.get(reverse('view_profile', kwargs={'user_id': user_b.id}))
        self.assertEqual(res_view.status_code, 200)
        self.assertContains(res_view, "M.Com Gold Medalist")

    def test_already_registered_error_messages_without_if(self):
        from users.validators import validate_unique_and_legitimate_email
        from users.forms import UserRegisterForm
        from django.core.exceptions import ValidationError

        User.objects.create_user(
            username="existinguser",
            password="StrongPass123!",
            email="existing@gmail.com",
            phone_number="9876543210",
        )

        with self.assertRaises(ValidationError) as ctx:
            validate_unique_and_legitimate_email("existing@gmail.com")
        self.assertIn("This email address is already registered.", str(ctx.exception))
        self.assertNotIn("If this email", str(ctx.exception))

        # Test phone number on form
        form = UserRegisterForm(data={'phone_number': '9876543210'})
        form.is_valid()
        self.assertIn('phone_number', form.errors)
        self.assertIn("This mobile number is already registered.", str(form.errors['phone_number']))
        self.assertNotIn("If this mobile", str(form.errors['phone_number']))


class NeedsReviewAdminApprovalTests(TestCase):
    def setUp(self):
        self.staff_admin = User.objects.create_user(
            username="staff_admin",
            password="AdminPassword123!",
            is_staff=True,
            is_approved=True,
            is_email_verified=True,
        )
        self.regular_user = User.objects.create_user(
            username="regular_user",
            password="UserPassword123!",
            is_staff=False,
            is_approved=True,
            is_email_verified=True,
        )
        self.edited_user = User.objects.create_user(
            username="edited_user",
            password="UserPassword123!",
            is_approved=True,
            is_phone_verified=True,
            is_email_verified=True,
            needs_review=True,
        )
        self.unapproved_user = User.objects.create_user(
            username="unapproved_user",
            password="UserPassword123!",
            is_approved=False,
            is_phone_verified=False,
            is_email_verified=False,
            needs_review=False,
        )

    def test_admin_dashboard_shows_edited_and_unapproved_users(self):
        self.client.login(username="staff_admin", password="AdminPassword123!")
        res = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "edited_user")
        self.assertContains(res, "unapproved_user")
        self.assertContains(res, "Edited (Needs Review)")

    def test_admin_dashboard_filter_edited_only(self):
        self.client.login(username="staff_admin", password="AdminPassword123!")
        res = self.client.get(reverse('admin_dashboard') + "?filter=edited")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "edited_user")
        self.assertNotContains(res, "unapproved_user")

    def test_admin_clear_review_approves_edit(self):
        self.client.login(username="staff_admin", password="AdminPassword123!")
        res = self.client.post(reverse('admin_clear_review', args=[self.edited_user.id]))
        self.assertRedirects(res, reverse('admin_dashboard'))
        self.edited_user.refresh_from_db()
        self.assertFalse(self.edited_user.needs_review)

    def test_admin_verify_user_clears_needs_review(self):
        self.client.login(username="staff_admin", password="AdminPassword123!")
        res = self.client.post(reverse('admin_verify_user', args=[self.edited_user.id]))
        self.assertRedirects(res, reverse('admin_dashboard'))
        self.edited_user.refresh_from_db()
        self.assertFalse(self.edited_user.needs_review)
        self.assertTrue(self.edited_user.is_approved)

    def test_regular_user_cannot_access_admin_endpoints(self):
        self.client.login(username="regular_user", password="UserPassword123!")
        res1 = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(res1.status_code, 302)
        res2 = self.client.post(reverse('admin_clear_review', args=[self.edited_user.id]))
        self.assertEqual(res2.status_code, 302)


class AdminReportDashboardAndContactAntiSpamTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.admin = User.objects.create_superuser(
            username="report_admin",
            password="AdminPass123!",
            email="admin_reports@example.com",
            phone_number="9876543210"
        )
        self.reporter = User.objects.create_user(
            username="vigilant_user",
            full_name="Vigilant User",
            password="UserPass123!",
            email="vigilant@example.com",
            phone_number="9876543211",
            is_approved=True
        )
        self.reported = User.objects.create_user(
            username="offensive_user",
            full_name="Offensive User",
            password="UserPass123!",
            email="offensive@example.com",
            phone_number="9876543212",
            is_approved=True
        )
        from communications.models import Report
        self.report = Report.objects.create(
            reporter=self.reporter,
            reported_user=self.reported,
            reason="User uploaded inappropriate profile images and abusive text."
        )

    def test_admin_dashboard_displays_report_details_and_reason(self):
        self.client.login(username="report_admin", password="AdminPass123!")
        res = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "offensive_user")
        self.assertContains(res, "vigilant_user")
        self.assertContains(res, "User uploaded inappropriate profile images and abusive text.")
        self.assertContains(res, "User Reports & Complaints")

    def test_admin_dismiss_report_removes_report(self):
        from communications.models import Report
        self.client.login(username="report_admin", password="AdminPass123!")
        res = self.client.post(reverse('admin_dismiss_report', args=[self.report.id]))
        self.assertRedirects(res, reverse('admin_dashboard'))
        self.assertFalse(Report.objects.filter(id=self.report.id).exists())

    def test_contact_form_spam_keyword_discarded_silently(self):
        from django.core import mail
        mail.outbox.clear()
        res = self.client.post(reverse('contact_us'), {
            'name': 'Kirk Balson',
            'email': 'domains@search-poorvanchalmatrimony.social',
            'message': 'Register poorvanchalmatrimony.social here: indexregister.live',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Your message has been sent successfully.")
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_form_telegram_spam_discarded_silently(self):
        from django.core import mail
        mail.outbox.clear()
        res = self.client.post(reverse('contact_us'), {
            'name': 'Davidtrawl',
            'email': 'no.reply.heinz@gmail.com',
            'message': 'Outreach through website contact forms. Telegram - https://t.me/FeedbackFormEU',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Your message has been sent successfully.")
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_form_probe_pattern_discarded_silently(self):
        from django.core import mail
        mail.outbox.clear()
        res = self.client.post(reverse('contact_us'), {
            'name': 'NARETGR1158760NERTHRRTH',
            'email': 'cesaru1998@notboxletters.com',
            'message': 'METRYTRE1158760MAWRERGTRH',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Your message has been sent successfully.")
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_form_phone_honeypot_discarded_silently(self):
        from django.core import mail
        mail.outbox.clear()
        res = self.client.post(reverse('contact_us'), {
            'name': 'Honest Inquirer',
            'email': 'honest@example.com',
            'message': 'Hello, I have a legitimate question.',
            'contact_phone_hp': '9876543210',
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Your message has been sent successfully.")
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_form_rapid_time_gate_discarded_silently(self):
        import time
        from django.core import mail
        from django.core.signing import TimestampSigner
        mail.outbox.clear()
        signer = TimestampSigner()
        # Simulated instant submission 0.1s after page load
        token = signer.sign(str(time.time() - 0.1))
        res = self.client.post(reverse('contact_us'), {
            'name': 'Fast Bot',
            'email': 'bot@example.com',
            'message': 'Fast automated submission.',
            'form_time': token,
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Your message has been sent successfully.")
        self.assertEqual(len(mail.outbox), 0)

    def test_guest_contact_otp_verification_flow(self):
        from django.core import mail
        from django.core.cache import cache
        mail.outbox.clear()

        # Step 1: Guest submits contact form
        res = self.client.post(reverse('contact_us'), {
            'name': 'Prospective Bride Family',
            'email': 'family@example.com',
            'message': 'We have a question regarding matching preferences in Siwan.',
        })
        self.assertRedirects(res, reverse('contact_verify'))

        # Verification email sent to guest, but NOT yet to admin
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['family@example.com'])
        self.assertIn("Verification Code for Your Inquiry", mail.outbox[0].subject)

        # Retrieve session token and pending data from cache
        session_token = self.client.session.get('contact_verify_token')
        self.assertIsNotNone(session_token)
        cache_key = f"contact_pending_{session_token}"
        pending_data = cache.get(cache_key)
        self.assertIsNotNone(pending_data)
        correct_otp = pending_data['code']

        # Step 2: Guest enters wrong code
        res_wrong = self.client.post(reverse('contact_verify'), {'code': '000000'})
        self.assertEqual(res_wrong.status_code, 200)
        self.assertContains(res_wrong, "Incorrect verification code")
        # Admin still has not received any inquiry
        self.assertEqual(len(mail.outbox), 1)

        # Step 3: Guest enters correct code
        res_correct = self.client.post(reverse('contact_verify'), {'code': correct_otp})
        self.assertEqual(res_correct.status_code, 200)
        self.assertContains(res_correct, "Your message has been sent successfully")

        # Admin now receives the inquiry email!
        from django.conf import settings
        expected_admin = getattr(settings, 'CONTACT_ADMIN_EMAIL', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@poorvanchalmatrimony.social')
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].to, [expected_admin])
        self.assertIn("[Verified Guest]", mail.outbox[1].subject)
        self.assertIn("Prospective Bride Family", mail.outbox[1].body)


class UserSuspensionDurationAndUnsuspendTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.staff_admin = User.objects.create_superuser(
            username="suspend_staff",
            password="AdminPass123!",
            email="staff@example.com",
            phone_number="9876543299"
        )
        self.target_user = User.objects.create_user(
            username="target_member",
            password="UserPass123!",
            email="target@example.com",
            phone_number="9876543298",
            full_name="Target Member",
            is_approved=True,
            is_email_verified=True,
            is_phone_verified=True
        )

    def test_admin_suspend_with_duration_and_reason(self):
        self.client.login(username="suspend_staff", password="AdminPass123!")
        res = self.client.post(reverse('admin_reject_user', args=[self.target_user.id]), {
            'days': '7',
            'reason': 'Multiple complaints of spam messages'
        })
        self.assertRedirects(res, reverse('admin_dashboard'))
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_suspended)
        self.assertFalse(self.target_user.is_approved)
        self.assertIsNotNone(self.target_user.suspended_until)
        self.assertEqual(self.target_user.suspension_reason, 'Multiple complaints of spam messages')

    def test_admin_suspend_indefinitely(self):
        self.client.login(username="suspend_staff", password="AdminPass123!")
        res = self.client.post(reverse('admin_reject_user', args=[self.target_user.id]), {
            'days': '',
            'reason': 'Severe violation'
        })
        self.assertRedirects(res, reverse('admin_dashboard'))
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_suspended)
        self.assertIsNone(self.target_user.suspended_until)

    def test_admin_unsuspend_user(self):
        from communications.models import Report
        Report.objects.create(
            reporter=self.staff_admin,
            reported_user=self.target_user,
            reason="Violation of guidelines"
        )
        self.assertEqual(Report.objects.filter(reported_user=self.target_user).count(), 1)

        self.target_user.is_suspended = True
        self.target_user.is_approved = False
        from django.utils import timezone
        from datetime import timedelta
        self.target_user.suspended_until = timezone.now() + timedelta(days=10)
        self.target_user.suspension_reason = "Temporary lockout"
        self.target_user.save()

        self.client.login(username="suspend_staff", password="AdminPass123!")
        res = self.client.post(reverse('admin_unsuspend_user', args=[self.target_user.id]))
        self.assertRedirects(res, reverse('admin_dashboard'))
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_suspended)
        self.assertTrue(self.target_user.is_approved)
        self.assertIsNone(self.target_user.suspended_until)
        self.assertEqual(self.target_user.suspension_reason, "")
        # Verify reports against the user were cleaned up
        self.assertEqual(Report.objects.filter(reported_user=self.target_user).count(), 0)

    def test_check_suspension_status_auto_lifts_expired_suspension(self):
        from communications.models import Report
        Report.objects.create(
            reporter=self.staff_admin,
            reported_user=self.target_user,
            reason="Past issue"
        )
        self.assertEqual(Report.objects.filter(reported_user=self.target_user).count(), 1)

        from django.utils import timezone
        from datetime import timedelta
        self.target_user.is_suspended = True
        self.target_user.is_approved = False
        self.target_user.suspended_until = timezone.now() - timedelta(minutes=5)
        self.target_user.suspension_reason = "Past lock"
        self.target_user.save()

        is_still_suspended = self.target_user.check_suspension_status()
        self.assertFalse(is_still_suspended)
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_suspended)
        self.assertTrue(self.target_user.is_approved)
        self.assertIsNone(self.target_user.suspended_until)
        # Verify reports against the user were cleaned up
        self.assertEqual(Report.objects.filter(reported_user=self.target_user).count(), 0)

    def test_lift_expired_suspensions_bulk(self):
        from communications.models import Report
        Report.objects.create(
            reporter=self.staff_admin,
            reported_user=self.target_user,
            reason="Bulk report"
        )
        self.assertEqual(Report.objects.filter(reported_user=self.target_user).count(), 1)

        from django.utils import timezone
        from datetime import timedelta
        self.target_user.is_suspended = True
        self.target_user.suspended_until = timezone.now() - timedelta(days=1)
        self.target_user.save()

        restored_count = User.lift_expired_suspensions()
        self.assertGreaterEqual(restored_count, 1)
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_suspended)
        # Verify reports were cleaned up
        self.assertEqual(Report.objects.filter(reported_user=self.target_user).count(), 0)

    def test_admin_dashboard_suspended_filter(self):
        self.target_user.is_suspended = True
        self.target_user.save()

        self.client.login(username="suspend_staff", password="AdminPass123!")
        res = self.client.get(reverse('admin_dashboard') + "?filter=suspended")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "target_member")
        self.assertContains(res, "Unsuspend &amp; Restore")

    def test_suspended_user_sees_reason_and_duration_on_login_and_views(self):
        from django.utils import timezone
        from datetime import timedelta
        future_date = timezone.now() + timedelta(days=7)
        self.target_user.is_suspended = True
        self.target_user.is_approved = False
        self.target_user.suspended_until = future_date
        self.target_user.suspension_reason = "Multiple complaints regarding inappropriate photos"
        self.target_user.save()

        # 1. Attempt login via POST
        res_login = self.client.post(reverse('login'), {
            'username': 'target_member',
            'password': 'UserPass123!'
        })
        self.assertEqual(res_login.status_code, 200)
        self.assertContains(res_login, "Your account has been suspended until")
        self.assertContains(res_login, "Multiple complaints regarding inappropriate photos")

        # 2. Authenticated suspended member hits active_member_required view
        self.client.force_login(self.target_user)
        res_member = self.client.get(reverse('profile_list'), follow=True)
        self.assertRedirects(res_member, reverse('home'))
        self.assertContains(res_member, "Your account is suspended until")
        self.assertContains(res_member, "Multiple complaints regarding inappropriate photos")

        # 3. Authenticated suspended member visits home page
        res_home = self.client.get(reverse('home'))
        self.assertEqual(res_home.status_code, 200)
        self.assertContains(res_home, "Account Suspended")
        self.assertContains(res_home, "Multiple complaints regarding inappropriate photos")
        self.assertContains(res_home, "Contact Support")

        # 4. Authenticated suspended member attempts edit_profile
        res_edit = self.client.get(reverse('edit_profile'), follow=True)
        self.assertRedirects(res_edit, reverse('home'))
        self.assertContains(res_edit, "Your account is suspended until")
        self.assertContains(res_edit, "Multiple complaints regarding inappropriate photos")





