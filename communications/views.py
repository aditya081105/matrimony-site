from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from datetime import date
from django.utils import timezone
from datetime import timedelta
from communications.models import Block, Report, RequestAttempt, ActivityLog

from .models import ContactRequest, SavedProfile
from users.models import CustomUser
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db import transaction

from django.utils.http import url_has_allowed_host_and_scheme

User = get_user_model()


def safe_redirect(request, fallback="profile_list"):
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return redirect(referer)
    return redirect(fallback)


@login_required
@require_POST
def send_request(request, user_id):
    is_htmx = bool(request.headers.get('HX-Request'))

    if request.user.is_suspended:
        if is_htmx:
            return render(request, "communications/includes/contact_button.html", {
                "target_user": CustomUser(id=user_id),
                "status": "none",
                "error_message": "Your account has been suspended."
            })
        messages.error(request, "Your account has been suspended.")
        return redirect("home")

    if not request.user.is_approved:
        if is_htmx:
            return render(request, "communications/includes/contact_button.html", {
                "target_user": CustomUser(id=user_id),
                "status": "none",
                "error_message": "Your account is pending approval."
            })
        messages.error(request, "Your account is pending approval.")
        return redirect('home')
    
    if not request.user.is_email_verified:
        if is_htmx:
            return render(request, "communications/includes/contact_button.html", {
                "target_user": CustomUser(id=user_id),
                "status": "none",
                "error_message": "Verify your email first."
            })
        messages.error(request, "Verify your email first.")
        return redirect("home")

    if not all([
        request.user.date_of_birth,
        request.user.height_cm,
        request.user.city,
        request.user.profile_photo,
    ]):
        if is_htmx:
            return render(request, "communications/includes/contact_button.html", {
                "target_user": CustomUser(id=user_id),
                "status": "none",
                "error_message": "Complete your profile before sending requests."
            })
        messages.error(request, "Complete your profile before sending requests.")
        return redirect("edit_profile")

    receiver = get_object_or_404(CustomUser, id=user_id)

    if receiver.is_staff or receiver.is_superuser:
        if is_htmx:
            return render(request, "communications/includes/contact_button.html", {
                "target_user": receiver,
                "status": "none",
                "error_message": "This account is unavailable."
            })
        messages.error(request, "This account is unavailable.")
        return redirect('profile_list')

    if ContactRequest.objects.filter(
        status="accepted"
    ).filter(
        Q(sender=request.user, receiver=receiver) |
        Q(sender=receiver, receiver=request.user)
    ).exists():
        if is_htmx:
            return render(request, "communications/includes/contact_button.html", {
                "target_user": receiver,
                "status": "accepted"
            })
        messages.info(request, "You are already matched with this user.")
        return redirect("profile_list")

    # Prevent sending request to yourself
    if receiver == request.user:
        return redirect("profile_list")

    if receiver.is_suspended:
        if is_htmx:
            return render(request, "communications/includes/contact_button.html", {
                "target_user": receiver,
                "status": "none",
                "error_message": "This account is unavailable."
            })
        messages.error(request, "This account is unavailable.")
        return redirect('profile_list')

    with transaction.atomic():
        # Acquire row-level lock on sender to serialize concurrent requests and prevent quota races
        CustomUser.objects.select_for_update().get(id=request.user.id)

        # Check block status inside transaction to prevent concurrency races
        is_blocked = Block.objects.filter(
            blocker=request.user,
            blocked=receiver
        ).exists() or Block.objects.filter(
            blocker=receiver,
            blocked=request.user
        ).exists()

        if is_blocked:
            if is_htmx:
                return render(request, "communications/includes/contact_button.html", {
                    "target_user": receiver,
                    "status": "none",
                    "error_message": "You cannot interact with this user."
                })
            messages.error(request, "You cannot interact with this user.")
            return redirect('profile_list')

        # Prevent duplicate requests in same direction
        if ContactRequest.objects.filter(sender=request.user, receiver=receiver, status='pending').exists():
            if is_htmx:
                return render(request, "communications/includes/contact_button.html", {
                    "target_user": receiver,
                    "status": "pending"
                })
            messages.info(request, "You have already sent a pending request to this user.")
            return redirect("profile_list")

        # If receiver already sent a request to request.user, auto-accept and connect both
        incoming = ContactRequest.objects.select_for_update().filter(
            sender=receiver, receiver=request.user, status='pending'
        ).first()

        if incoming:
            incoming.status = 'accepted'
            incoming.save()
            ContactRequest.objects.update_or_create(
                sender=request.user,
                receiver=receiver,
                defaults={'status': 'accepted', 'attempt_count': 1}
            )
            ActivityLog.objects.create(
                user=request.user,
                target_user=receiver,
                action='accept_request'
            )
            if is_htmx:
                return render(request, "communications/includes/contact_button.html", {
                    "target_user": receiver,
                    "status": "accepted"
                })
            messages.success(request, f"It's a match! You and {receiver.full_name} are now connected.")
            return safe_redirect(request, "profile_list")

        today = timezone.now().date()
        total_daily_attempts = RequestAttempt.objects.filter(
            sender=request.user,
            created_at__date=today
        ).count()

        receiver_daily_attempts = RequestAttempt.objects.filter(
            sender=request.user,
            receiver=receiver,
            created_at__date=today
        ).count()

        is_admin = bool(request.user.is_staff or request.user.is_superuser)

        if not is_admin and receiver_daily_attempts >= 3:
            err_msg = f"Daily contact limit (3) reached for {receiver.full_name or receiver.username}."
            if is_htmx:
                return render(request, "communications/includes/contact_button.html", {
                    "target_user": receiver,
                    "status": "none",
                    "error_message": err_msg
                })
            messages.error(
                request,
                f"For member safety and privacy, you can only send up to 3 contact attempts to {receiver.full_name or receiver.username} in a single day. You can still send contact requests to other profiles."
            )
            return redirect('profile_list')

        tier = (request.user.membership_tier or '').lower()
        if is_admin:
            daily_limit = 999999
        elif not request.user.is_premium:
            daily_limit = 3
        elif tier == 'silver':
            daily_limit = 10
        else:
            daily_limit = 999999

        if total_daily_attempts >= daily_limit:
            tier_name = "Silver" if tier == "silver" else "Free"
            err_msg = f"Daily contact limit of {daily_limit} reached for your {tier_name} plan."
            if is_htmx:
                return render(request, "communications/includes/contact_button.html", {
                    "target_user": receiver,
                    "status": "none",
                    "error_message": err_msg
                })
            messages.error(
                request,
                f"Daily contact request limit of {daily_limit} reached for your {tier_name} plan. Upgrade to Gold for unlimited requests."
            )
            return redirect('profile_list')

        RequestAttempt.objects.create(
            sender=request.user,
            receiver=receiver
        )

        ContactRequest.objects.update_or_create(
            sender=request.user,
            receiver=receiver,
            defaults={'status': 'pending', 'attempt_count': receiver_daily_attempts + 1}
        )

        ActivityLog.objects.create(
            user=request.user,
            target_user=receiver,
            action='send_request'
        )

    if is_htmx:
        return render(request, "communications/includes/contact_button.html", {
            "target_user": receiver,
            "status": "pending"
        })
    messages.success(request, f"Contact request sent to {receiver.full_name}.")
    return safe_redirect(request, "profile_list")

@login_required
@require_POST
def update_request(request, request_id, action):
    with transaction.atomic():
        contact_request = get_object_or_404(
            ContactRequest.objects.select_for_update(),
            id=request_id,
            receiver=request.user
        )

        if contact_request.status != 'pending':
            if request.headers.get('HX-Request'):
                return render(request, 'communications/includes/request_action_status.html', {'contact_request': contact_request})
            messages.info(request, "This request has already been processed.")
            return redirect('received_requests')

        if action == 'accept':
            contact_request.status = 'accepted'
            ContactRequest.objects.filter(
                sender=request.user,
                receiver=contact_request.sender
            ).update(status='accepted')
            ActivityLog.objects.create(
                user=request.user,
                target_user=contact_request.sender,
                action='accept_request'
            )
        elif action == 'reject':
            contact_request.status = 'rejected'
            ActivityLog.objects.create(
                user=request.user,
                target_user=contact_request.sender,
                action='reject_request'
            )

        contact_request.save()

    if request.headers.get('HX-Request'):
        return render(request, 'communications/includes/request_action_status.html', {'contact_request': contact_request})
    return redirect('received_requests')

@login_required
def received_requests(request):
    requests = request.user.received_requests.filter(
        status='pending'
    ).select_related('sender').order_by('-created_at')

    return render(request, 'communications/received_requests.html', {
        'requests': requests
    })

@login_required
@require_POST
def unmatch(request, user_id):
    target = get_object_or_404(CustomUser, id=user_id)
    ContactRequest.objects.filter(
        Q(sender=request.user, receiver=target) |
        Q(sender=target, receiver=request.user)
    ).delete()

    ActivityLog.objects.create(
        user=request.user,
        target_user=target,
        action='unmatch'
    )

    messages.success(request, "Match removed.")
    return redirect('profile_list')

@login_required
@require_POST
def cancel_request(request, user_id):
    receiver = get_object_or_404(CustomUser, id=user_id)
    ContactRequest.objects.filter(
        sender=request.user,
        receiver=receiver,
        status='pending'
    ).delete()

    if request.headers.get('HX-Request'):
        return render(request, "communications/includes/contact_button.html", {
            "target_user": receiver,
            "status": "none"
        })

    messages.success(request, "Request cancelled.")
    return safe_redirect(request, 'profile_list')

@login_required
@require_POST
def block_user(request, user_id):

    if request.user.is_suspended:
        messages.error(request, "Your account has been suspended.")
        return redirect("home")
    
    target = get_object_or_404(CustomUser, id=user_id)

    if target.is_staff or target.is_superuser:
        messages.error(request, "This account is unavailable.")
        return redirect('profile_list')

    if target == request.user:
        return redirect('profile_list')

    Block.objects.get_or_create(
        blocker=request.user,
        blocked=target
    )

    # Delete any existing requests in both directions
    ContactRequest.objects.filter(
        Q(sender=request.user, receiver=target) |
        Q(sender=target, receiver=request.user)
    ).delete()

    # Remove bookmarks in both directions
    SavedProfile.objects.filter(
        Q(user=request.user, saved_user=target) |
        Q(user=target, saved_user=request.user)
    ).delete()

    ActivityLog.objects.create(
        user=request.user,
        target_user=target,
        action='block_user'
    )

    if request.headers.get('HX-Request'):
        return HttpResponse(
            '<div class="col-lg-4 col-md-6 mb-4">'
            '<div class="card border-0 rounded-4 p-4 text-center bg-light text-muted small shadow-sm">'
            'Profile blocked and removed from view.'
            '</div></div>'
        )

    messages.success(request, "User blocked.")
    return redirect('profile_list')

@login_required
def report_user(request, user_id):

    if request.user.is_suspended:
        messages.error(request, "Your account has been suspended.")
        return redirect("home")

    target = get_object_or_404(CustomUser, id=user_id)

    if target.is_staff or target.is_superuser:
        messages.error(request, "This account is unavailable.")
        return redirect('profile_list')

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()

        Report.objects.create(
            reporter=request.user,
            reported_user=target,
            reason=reason
        )

        ActivityLog.objects.create(
            user=request.user,
            target_user=target,
            action='report_user'
        )

        report_count = Report.objects.filter(
            reported_user=target
        ).count()

        if report_count >= 5:
            target.is_suspended = True
            target.save()

        messages.success(request, "User reported to administrators.")
        return redirect('profile_list')

    return render(request, "communications/report_user.html", {
        "target": target
    })

@login_required
def blocked_users(request):
    blocked = Block.objects.filter(
        blocker=request.user
    ).select_related('blocked')

    return render(request, 'communications/blocked_users.html', {
        'blocked_users': blocked
    })


@login_required
@require_POST
def unblock_user(request, user_id):
    Block.objects.filter(
        blocker=request.user,
        blocked_id=user_id
    ).delete()

    messages.success(request, "User unblocked.")
    return redirect('blocked_users')

@login_required
@require_POST
def toggle_save(request, user_id):

    if request.user.is_suspended:
        messages.error(request, "Your account has been suspended.")
        return redirect("home")

    target = get_object_or_404(CustomUser, id=user_id)

    if (target.is_staff or target.is_superuser) and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "This account is unavailable.")
        return redirect('profile_list')

    obj, created = SavedProfile.objects.get_or_create(
        user=request.user,
        saved_user=target
    )

    if not created:
        obj.delete()

    if request.headers.get('HX-Request'):
        return render(request, 'communications/includes/save_button.html', {
            'target_id': target.id,
            'is_saved': created
        })

    return safe_redirect(request, "profile_list")


@login_required
def saved_profiles(request):

    blocked_by_me = Block.objects.filter(
        blocker=request.user
    ).values_list("blocked_id", flat=True)

    blocked_me = Block.objects.filter(
        blocked=request.user
    ).values_list("blocker_id", flat=True)

    blocked_ids = list(blocked_by_me) + list(blocked_me)

    saved = SavedProfile.objects.filter(
        user=request.user
    ).exclude(saved_user_id__in=blocked_ids).select_related("saved_user")

    users = [s.saved_user for s in saved]

    return render(request, "users/saved_profiles.html", {
        "saved_users": users
    })