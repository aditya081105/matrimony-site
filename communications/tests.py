from django.test import TestCase, TransactionTestCase, Client, skipUnlessDBFeature
from django.db import connection
from django.urls import reverse
import threading
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
        self.client.post(reverse("send_request", args=[self.user1.id]))

        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_blocked_user_cannot_send_request(self):
        Block.objects.create(
            blocker=self.user2,
            blocked=self.user1,
        )

        self.client.post(reverse("send_request", args=[self.user2.id]))

        self.assertEqual(ContactRequest.objects.count(), 0)

    def test_unblock_removes_block(self):
        Block.objects.create(
            blocker=self.user1,
            blocked=self.user2,
        )

        self.client.post(reverse("unblock_user", args=[self.user2.id]))

        self.assertFalse(
            Block.objects.filter(
                blocker=self.user1,
                blocked=self.user2,
            ).exists()
        )

    def test_toggle_save(self):
        self.client.post(reverse("toggle_save", args=[self.user2.id]))

        self.assertEqual(SavedProfile.objects.count(), 1)

        self.client.post(reverse("toggle_save", args=[self.user2.id]))

        self.assertEqual(SavedProfile.objects.count(), 0)

    def test_cannot_interact_with_admin_account(self):
        admin = CustomUser.objects.create_superuser(
            username="comm_admin",
            email="commadmin@test.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=True
        )

        # Cannot send request to admin
        res_req = self.client.post(reverse("send_request", args=[admin.id]))
        self.assertEqual(res_req.status_code, 302)
        self.assertEqual(ContactRequest.objects.filter(receiver=admin).count(), 0)

        # Cannot save admin profile
        res_save = self.client.post(reverse("toggle_save", args=[admin.id]))
        self.assertEqual(res_save.status_code, 302)
        self.assertEqual(SavedProfile.objects.filter(saved_user=admin).count(), 0)

    def test_duplicate_request_not_created(self):
        ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status="pending",
            attempt_count=1,
        )

        response = self.client.post(
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

        response = self.client.post(
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

        response = self.client.post(
            reverse("send_request", args=[self.user2.id])
        )

        self.assertEqual(response.status_code, 302)

    def test_request_blocked_at_daily_limit(self):
        for _ in range(3):
            RequestAttempt.objects.create(
                sender=self.user1,
                receiver=self.user2,
            )

        self.client.post(reverse("send_request", args=[self.user2.id]))

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
        response = self.client.post(reverse("send_request", args=[self.user2.id]))
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
        self.client.post(reverse("unmatch", args=[self.user2.id]))
        self.assertEqual(ContactRequest.objects.count(), 0)
        self.assertTrue(ActivityLog.objects.filter(user=self.user1, target_user=self.user2, action='unmatch').exists())

    def test_block_removes_saved_profiles_bidirectionally(self):
        SavedProfile.objects.create(user=self.user1, saved_user=self.user2)
        SavedProfile.objects.create(user=self.user2, saved_user=self.user1)
        self.client.post(reverse("block_user", args=[self.user2.id]))
        self.assertEqual(SavedProfile.objects.count(), 0)

    def test_state_mutating_endpoints_reject_get_requests(self):
        # Enforce HTTP 405 Method Not Allowed on plain GET requests
        for endpoint, args in [
            ("send_request", [self.user2.id]),
            ("block_user", [self.user2.id]),
            ("unblock_user", [self.user2.id]),
            ("unmatch", [self.user2.id]),
            ("cancel_request", [self.user2.id]),
            ("toggle_save", [self.user2.id]),
        ]:
            response = self.client.get(reverse(endpoint, args=args))
            self.assertEqual(
                response.status_code, 405,
                f"Endpoint {endpoint} allowed GET but must require POST"
            )

    def test_send_request_htmx(self):
        response = self.client.post(
            reverse("send_request", args=[self.user2.id]),
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "communications/includes/contact_button.html")
        self.assertContains(response, "Request Pending")
        self.assertContains(response, "Cancel Request")

    def test_cancel_request_htmx(self):
        ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status="pending"
        )
        response = self.client.post(
            reverse("cancel_request", args=[self.user2.id]),
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "communications/includes/contact_button.html")
        self.assertContains(response, "Request Contact")

    def test_toggle_save_htmx(self):
        # First toggle: Save
        response = self.client.post(
            reverse("toggle_save", args=[self.user2.id]),
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "communications/includes/save_button.html")
        self.assertContains(response, "Remove Saved")

        # Second toggle: Unsave
        response2 = self.client.post(
            reverse("toggle_save", args=[self.user2.id]),
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response2.status_code, 200)
        self.assertContains(response2, "Save Profile")

    def test_update_request_accept_htmx(self):
        req = ContactRequest.objects.create(
            sender=self.user2,
            receiver=self.user1,
            status="pending"
        )
        response = self.client.post(
            reverse("update_request", args=[req.id, "accept"]),
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "communications/includes/request_action_status.html")
        self.assertContains(response, "Accepted - Contact Unlocked")

    def test_block_user_htmx(self):
        response = self.client.post(
            reverse("block_user", args=[self.user2.id]),
            HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile blocked")

    def test_send_request_sticky_rejection(self):
        # User 1 sends request to User 2, and User 2 rejects it
        req = ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status="rejected",
            attempt_count=1
        )
        # User 1 tries to send another request to User 2
        response = self.client.post(reverse("send_request", args=[self.user2.id]))
        self.assertEqual(response.status_code, 302)
        # Request status must remain rejected and not reset to pending
        req.refresh_from_db()
        self.assertEqual(req.status, "rejected")

    def test_cannot_send_request_to_unapproved_or_suspended_user(self):
        unapproved = CustomUser.objects.create_user(
            username="unapproved_target",
            email="unapproved_target@test.com",
            password="Test12345!",
            is_approved=False,
            is_active=True,
            is_email_verified=True,
            gender="F",
            phone_number="8888888801",
            date_of_birth="2000-01-01",
            city=self.city,
            profile_photo="test.jpg",
        )
        res = self.client.post(reverse("send_request", args=[unapproved.id]))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(ContactRequest.objects.filter(receiver=unapproved).count(), 0)

        suspended = CustomUser.objects.create_user(
            username="suspended_target",
            email="suspended_target@test.com",
            password="Test12345!",
            is_approved=True,
            is_active=True,
            is_suspended=True,
            is_email_verified=True,
            gender="F",
            phone_number="8888888802",
            date_of_birth="2000-01-01",
            city=self.city,
            profile_photo="test.jpg",
        )
        res2 = self.client.post(reverse("send_request", args=[suspended.id]))
        self.assertEqual(res2.status_code, 302)
        self.assertEqual(ContactRequest.objects.filter(receiver=suspended).count(), 0)

    def test_duplicate_report_blocked(self):
        from communications.models import Report
        # First report
        res1 = self.client.post(reverse("report_user", args=[self.user2.id]), {"reason": "Spam"})
        self.assertEqual(res1.status_code, 302)
        self.assertEqual(Report.objects.filter(reporter=self.user1, reported_user=self.user2).count(), 1)

        # Second report by same user must be rejected
        res2 = self.client.post(reverse("report_user", args=[self.user2.id]), {"reason": "Harassment"})
        self.assertEqual(res2.status_code, 302)
        self.assertEqual(Report.objects.filter(reporter=self.user1, reported_user=self.user2).count(), 1)

    def test_reporting_requires_5_distinct_approved_reporters_to_suspend(self):
        from communications.models import Report
        # Target starts unsuspended
        self.assertFalse(self.user2.is_suspended)

        # Create 4 approved distinct reporters
        reporters = []
        for i in range(4):
            rep = CustomUser.objects.create_user(
                username=f"reporter_{i}",
                email=f"reporter_{i}@test.com",
                password="TestPassword123!",
                is_approved=True,
                is_active=True,
                is_email_verified=True,
                gender="M",
                phone_number=f"777777770{i}",
            )
            reporters.append(rep)

        # User 1 reports User 2
        self.client.post(reverse("report_user", args=[self.user2.id]), {"reason": "Violation"})
        self.user2.refresh_from_db()
        self.assertFalse(self.user2.is_suspended)

        # 3 more distinct reporters report User 2 (total 4 distinct)
        for rep in reporters[:3]:
            c = Client()
            c.login(username=rep.username, password="TestPassword123!")
            c.post(reverse("report_user", args=[self.user2.id]), {"reason": "Violation"})

        self.user2.refresh_from_db()
        self.assertFalse(self.user2.is_suspended)

        # 5th distinct approved reporter reports User 2 -> auto suspended
        c5 = Client()
        c5.login(username=reporters[3].username, password="TestPassword123!")
        c5.post(reverse("report_user", args=[self.user2.id]), {"reason": "Violation"})

        self.user2.refresh_from_db()
        self.assertTrue(self.user2.is_suspended)

    def test_reporting_cannot_suspend_admin(self):
        admin = CustomUser.objects.create_superuser(
            username="immune_admin",
            email="immune_admin@test.com",
            password="AdminPassword123!",
            is_staff=True,
            is_superuser=True
        )
        res = self.client.post(reverse("report_user", args=[admin.id]), {"reason": "Spam"})
        self.assertEqual(res.status_code, 302)
        admin.refresh_from_db()
        self.assertFalse(admin.is_suspended)

    def test_unmatch_only_works_for_accepted_match(self):
        # User 1 has rejected request to User 2
        req = ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status="rejected",
            attempt_count=1
        )
        # Attempt to call unmatch to wipe rejection
        res = self.client.post(reverse("unmatch", args=[self.user2.id]))
        self.assertEqual(res.status_code, 302)
        # Rejected request must NOT be deleted
        self.assertTrue(ContactRequest.objects.filter(id=req.id, status="rejected").exists())

    def test_block_preserves_sticky_rejection(self):
        # User 1's request to User 2 was rejected
        req = ContactRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            status="rejected",
            attempt_count=1
        )
        # User 1 blocks User 2
        self.client.post(reverse("block_user", args=[self.user2.id]))
        # Rejected request must NOT be deleted
        self.assertTrue(ContactRequest.objects.filter(id=req.id, status="rejected").exists())

        # User 1 unblocks User 2
        self.client.post(reverse("unblock_user", args=[self.user2.id]))
        # Sending request again must STILL be blocked by sticky rejection
        res = self.client.post(reverse("send_request", args=[self.user2.id]))
        self.assertEqual(res.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, "rejected")

    def test_suspended_user_pending_request_cannot_be_accepted_and_hidden_from_received(self):
        # User 2 sends request to User 1
        req = ContactRequest.objects.create(
            sender=self.user2,
            receiver=self.user1,
            status="pending"
        )
        # User 2 gets suspended
        self.user2.is_suspended = True
        self.user2.save()

        # 1. Received requests list must not show suspended sender
        res_list = self.client.get(reverse("received_requests"))
        self.assertEqual(res_list.status_code, 200)
        self.assertNotIn(req, res_list.context["requests"])

        # 2. Attempting to accept request must fail
        res_accept = self.client.post(reverse("update_request", args=[req.id, "accept"]))
        self.assertEqual(res_accept.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, "pending")  # Must NOT be accepted

    def test_report_reason_length_capped(self):
        from communications.models import Report
        long_reason = "A" * 2500
        res = self.client.post(reverse("report_user", args=[self.user2.id]), {"reason": long_reason})
        self.assertEqual(res.status_code, 302)
        report = Report.objects.get(reporter=self.user1, reported_user=self.user2)
        self.assertLessEqual(len(report.reason), 1000)


@skipUnlessDBFeature('has_select_for_update')
class CommunicationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.city = City.objects.create(name="Delhi")
        self.user1 = CustomUser.objects.create_user(
            username="concurrent_user1",
            email="concurrent1@test.com",
            password="Test12345!",
            full_name="User One",
            gender="M",
            phone_number="9999999991",
            is_approved=True,
            is_email_verified=True,
            date_of_birth="2000-01-01",
            height_cm=170,
            city=self.city,
            profile_photo="test.jpg",
        )
        self.user2 = CustomUser.objects.create_user(
            username="concurrent_user2",
            email="concurrent2@test.com",
            password="Test12345!",
            full_name="User Two",
            gender="F",
            phone_number="8888888882",
            is_approved=True,
            is_email_verified=True,
            date_of_birth="2000-01-01",
            height_cm=165,
            city=self.city,
            profile_photo="test.jpg",
        )
        self.user3 = CustomUser.objects.create_user(
            username="concurrent_user3",
            email="concurrent3@test.com",
            password="Test12345!",
            full_name="User Three",
            gender="F",
            phone_number="8888888883",
            is_approved=True,
            is_email_verified=True,
            date_of_birth="2000-01-01",
            height_cm=165,
            city=self.city,
            profile_photo="test.jpg",
        )
        self.user4 = CustomUser.objects.create_user(
            username="concurrent_user4",
            email="concurrent4@test.com",
            password="Test12345!",
            full_name="User Four",
            gender="F",
            phone_number="8888888884",
            is_approved=True,
            is_email_verified=True,
            date_of_birth="2000-01-01",
            height_cm=165,
            city=self.city,
            profile_photo="test.jpg",
        )

    def test_concurrent_quota_race_condition_prevention(self):
        # User 1 is on free tier (daily limit = 3).
        # Pre-populate 2 attempts so only 1 attempt remains.
        RequestAttempt.objects.create(sender=self.user1, receiver=self.user4)
        RequestAttempt.objects.create(sender=self.user1, receiver=self.user4)

        errors = []
        clients = []
        for _ in range(2):
            c = Client()
            c.force_login(self.user1)
            clients.append(c)

        targets = [self.user2, self.user3]

        def attempt_send(c, target):
            try:
                c.post(reverse("send_request", args=[target.id]))
            except Exception as e:
                errors.append(e)
            finally:
                connection.close()

        threads = [
            threading.Thread(target=attempt_send, args=(clients[i], targets[i]))
            for i in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        # Exactly 3 total daily attempts allowed (2 initial + 1 successful from threads)
        self.assertEqual(RequestAttempt.objects.filter(sender=self.user1).count(), 3)
        # Exactly 1 new ContactRequest created (the other was rejected by quota)
        self.assertEqual(
            ContactRequest.objects.filter(sender=self.user1).filter(
                receiver__in=[self.user2, self.user3]
            ).count(),
            1
        )