from functools import wraps
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse


def active_member_required(view_func):
    """
    Central access gate for active matrimony platform features.
    Guarantees that:
    1. The user is authenticated.
    2. Admins/staff pass through with full moderation capabilities.
    3. Suspended users are immediately blocked from all member features.
    4. Unapproved users are shown the pending approval notice.
    5. Unverified email users are shown the email verification required notice.
    Supports both standard HTTP requests and HTMX requests gracefully.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        is_admin = bool(request.user.is_staff or request.user.is_superuser)
        if is_admin:
            return view_func(request, *args, **kwargs)

        if request.user.is_suspended:
            if request.user.check_suspension_status():
                if request.user.suspended_until:
                    until_str = request.user.suspended_until.strftime('%b %d, %Y')
                    suspension_msg = f"Your account is suspended until {until_str}. Please contact support if you need assistance."
                else:
                    suspension_msg = "Your account has been suspended indefinitely. Please contact support."
                if request.headers.get('HX-Request'):
                    return HttpResponse(
                        f'<div class="alert alert-danger text-center p-3 rounded-4 shadow-sm">{suspension_msg}</div>',
                        status=403
                    )
                messages.error(request, suspension_msg)
                return redirect("home")

        if not request.user.is_approved:
            if request.headers.get('HX-Request'):
                return render(request, "users/pending_approval.html", status=403)
            return render(request, "users/pending_approval.html")

        if not request.user.is_email_verified:
            if request.headers.get('HX-Request'):
                return render(request, "users/verify_email_required.html", status=403)
            return render(request, "users/verify_email_required.html")

        return view_func(request, *args, **kwargs)

    return _wrapped_view
