from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from datetime import date
from django.utils import timezone
from datetime import timedelta
from communications.models import Block, Report, RequestAttempt, ActivityLog

from .models import ContactRequest, SavedProfile
from users.models import CustomUser
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

@login_required
def send_request(request, user_id):

    if not request.user.is_approved:
        messages.error(request, "Your account is pending approval.")
        return redirect('home')

    if not all([
        request.user.date_of_birth,
        request.user.height_cm,
        request.user.city,
        request.user.profile_photo,
    ]):
        messages.error(request, "Complete your profile before sending requests.")
        return redirect("edit_profile")

    receiver = get_object_or_404(CustomUser, id=user_id)

    # Prevent sending request to yourself
    if receiver == request.user:
        return redirect("profile_list")

    # Prevent duplicate requests
    if ContactRequest.objects.filter(sender=request.user, receiver=receiver).exists():
        return redirect("profile_list")

    if receiver.is_suspended:
        messages.error(request, "This account is unavailable.")
        return redirect('profile_list')

    is_blocked = Block.objects.filter(
        blocker=request.user,
        blocked=receiver
    ).exists() or Block.objects.filter(
        blocker=receiver,
        blocked=request.user
    ).exists()

    if is_blocked:
        messages.error(request, "You cannot interact with this user.")
        return redirect('profile_list')
    
    if Block.objects.filter(blocker=request.user, blocked=receiver).exists():
        return redirect("profile_list")

    if receiver == request.user:
        return redirect('profile_list')

    today = date.today()

    # ONLY check requests where current user is sender
    existing = ContactRequest.objects.filter(
        sender=request.user,
        receiver=receiver
    ).first()

    if existing:
        # reset daily attempts if new day
        if existing.created_at.date() != today:
            existing.attempt_count = 1
        else:
            existing.attempt_count += 1

        if existing.attempt_count > 3:
            messages.error(request, "Daily request limit reached for this user.")
            return redirect('profile_list')

        existing.status = 'pending'
        existing.save()
        return redirect('profile_list')

    today = timezone.now().date()

    daily_attempts = RequestAttempt.objects.filter(
        sender=request.user,
        receiver=receiver,
        created_at__date=today
    ).count()

    if daily_attempts >= 3:
        messages.error(request, "Daily request limit reached for this user.")
        return redirect('profile_list')
    
    RequestAttempt.objects.create(
        sender=request.user,
        receiver=receiver
    )
    # If no request in THIS direction, create new one
    ContactRequest.objects.create(
        sender=request.user,
        receiver=receiver,
        status='pending',
        attempt_count=1
    )

    ActivityLog.objects.create(
        user=request.user,
        target_user=receiver,
        action='send_request'
    )
    
    return redirect(request.META.get("HTTP_REFERER", "profile_list"))

@login_required
def update_request(request, request_id, action):
    contact_request = get_object_or_404(
        ContactRequest,
        id=request_id,
        receiver=request.user
    )

    if action == 'accept':
        contact_request.status = 'accepted'
    elif action == 'reject':
        contact_request.status = 'rejected'

    if action == 'accept':
        ActivityLog.objects.create(
            user=request.user,
            target_user=contact_request.sender,
            action='accept_request'
        )

    elif action == 'reject':
        ActivityLog.objects.create(
            user=request.user,
            target_user=contact_request.sender,
            action='reject_request'
        )

    contact_request.save()
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
def unmatch(request, user_id):
    ContactRequest.objects.filter(
        status='accepted'
    ).filter(
        sender=request.user,
        receiver_id=user_id
    ).delete()

    ContactRequest.objects.filter(
        status='accepted'
    ).filter(
        sender_id=user_id,
        receiver=request.user
    ).delete()

    messages.success(request, "Match removed.")
    return redirect('profile_list')

from django.shortcuts import redirect
from django.contrib import messages

@login_required
def cancel_request(request, user_id):
    print("CANCEL VIEW TRIGGERED")
    ContactRequest.objects.filter(
        sender=request.user,
        receiver_id=user_id,
        status='pending'
    ).delete()

    messages.success(request, "Request cancelled.")

    # Go back to previous page
    return redirect(request.META.get('HTTP_REFERER', 'profile_list'))

@login_required
def block_user(request, user_id):
    target = get_object_or_404(CustomUser, id=user_id)

    if target == request.user:
        return redirect('profile_list')

    Block.objects.get_or_create(
        blocker=request.user,
        blocked=target
    )

    # Delete any existing requests in both directions
    ContactRequest.objects.filter(
        sender=request.user,
        receiver=target
    ).delete()

    ContactRequest.objects.filter(
        sender=target,
        receiver=request.user
    ).delete()

    SavedProfile.objects.filter(
        user=request.user,
        saved_user=target
    ).delete()

    messages.success(request, "User blocked.")

    ActivityLog.objects.create(
        user=request.user,
        target_user=target,
        action='block_user'
    )

    return redirect('profile_list')

@login_required
def report_user(request, user_id):
    target = get_object_or_404(CustomUser, id=user_id)

    if request.method == "POST":
        reason = request.POST.get("reason", "")

        Report.objects.create(
            reporter=request.user,
            reported_user=target,
            reason=reason
        )

        messages.success(request, "User reported.")
        return redirect('profile_list')
    
    report_count = Report.objects.filter(
        reported_user=target
    ).count()

    if report_count >= 5:
        target.is_suspended = True
        target.save()
    
    ActivityLog.objects.create(
        user=request.user,
        target_user=target,
        action='report_user'
    )

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
def unblock_user(request, user_id):
    Block.objects.filter(
        blocker=request.user,
        blocked_id=user_id
    ).delete()

    messages.success(request, "User unblocked.")
    return redirect('blocked_users')

@login_required
def toggle_save(request, user_id):

    target = get_object_or_404(CustomUser, id=user_id)

    obj, created = SavedProfile.objects.get_or_create(
        user=request.user,
        saved_user=target
    )

    if not created:
        obj.delete()

    return redirect(request.META.get("HTTP_REFERER", "profile_list"))


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