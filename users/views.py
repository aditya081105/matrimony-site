from datetime import date
import random
import time
from django.db.models import Q, Count, Case, When, Value, IntegerField
from django.utils import timezone
from django.db import models
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.contrib.auth import logout
from communications.models import Block, ContactRequest, ActivityLog, Report, SavedProfile
from django.http import HttpResponse, Http404
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.conf import settings
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from core.utils import get_client_ip, get_ip_network_key

from django.contrib.admin.views.decorators import staff_member_required
from django.utils.http import url_has_allowed_host_and_scheme
from users.decorators import active_member_required
from users.visibility import visible_profiles, can_view, get_profile_privacy_context
from .models import CustomUser, Caste, City, Profile
from .forms import UserRegisterForm, UserUpdateForm
from core.services import send_verification_email

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.is_active = True # Allow login immediately
            user.save()

            try:
                send_verification_email(request, user)

            except Exception as e:
                print(f"Email error: {e}") # Log it to Render logs, don't crash

            login(request, user)
            request.session['last_email_verification_sent'] = time.time()

            messages.success(
                request,
                f"Welcome to Poorvanchal Matrimony, {user.full_name or user.username}! Your profile has been created successfully."
            )

            return redirect("home")
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})


# Keep your profile_list and contact_view below this...

from django.db.models import Q

@active_member_required
def profile_list(request):
    is_admin = bool(request.user.is_staff or request.user.is_superuser)

    from core.caching import get_cached_cities, get_cached_castes
    cities = get_cached_cities()
    castes = get_cached_castes()

    now = timezone.now()
    active_sub_filter = Q(subscription__is_active=True) & (
        Q(subscription__expires_at__isnull=True) | Q(subscription__expires_at__gt=now)
    )

    profiles = visible_profiles(request.user).annotate(
        tier_weight=Case(
            When(active_sub_filter, subscription__plan__code='diamond', then=Value(3)),
            When(active_sub_filter, subscription__plan__code='gold', then=Value(2)),
            When(active_sub_filter, subscription__plan__code='silver', then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        )
    ).select_related('profile', 'city', 'caste_community', 'subscription', 'subscription__plan').order_by('-tier_weight', '-date_joined')

    # Gender filter handling
    user_gender = getattr(request.user, 'gender', None)
    opposite_gender = 'F' if user_gender == 'M' else ('M' if user_gender == 'F' else '')

    if 'gender' not in request.GET:
        selected_gender = 'any' if is_admin else (opposite_gender if opposite_gender else 'any')
    else:
        raw_gender = request.GET.get('gender', '').strip()
        if raw_gender in ['M', 'F']:
            selected_gender = raw_gender
        else:
            selected_gender = 'any'

    if selected_gender in ['M', 'F']:
        profiles = profiles.filter(gender=selected_gender)
    caste_query = request.GET.get('caste', '').strip()
    if caste_query:
        if caste_query.isdigit():
            profiles = profiles.filter(
                Q(caste_community_id=int(caste_query)) |
                Q(caste__icontains=caste_query) |
                Q(sub_caste__icontains=caste_query)
            )
        else:
            profiles = profiles.filter(
                Q(caste__icontains=caste_query) |
                Q(sub_caste__icontains=caste_query) |
                Q(caste_community__name__icontains=caste_query)
            )
    city_param = (request.GET.get('city') or '').strip()
    if city_param:
        try:
            city_id = int(city_param)
            profiles = profiles.filter(city_id=city_id)
        except (ValueError, TypeError):
            pass
    if request.GET.get('min_height'):
        try:
            min_h = int(request.GET.get('min_height'))
            profiles = profiles.filter(height_cm__gte=min_h)
        except (ValueError, TypeError):
            pass
    if request.GET.get('max_height'):
        try:
            max_h = int(request.GET.get('max_height'))
            profiles = profiles.filter(height_cm__lte=max_h)
        except (ValueError, TypeError):
            pass

    today = date.today()
    if request.GET.get('min_age'):
        try:
            min_age = int(request.GET.get('min_age'))
            try:
                max_dob = date(today.year - min_age, today.month, today.day)
            except ValueError:
                max_dob = date(today.year - min_age, today.month, 28)
            profiles = profiles.filter(date_of_birth__lte=max_dob)
        except (ValueError, TypeError):
            pass
    if request.GET.get('max_age'):
        try:
            max_age = int(request.GET.get('max_age'))
            try:
                # Age <= max_age means the person has not yet reached their (max_age + 1)th birthday
                min_dob = date(today.year - (max_age + 1), today.month, today.day)
            except ValueError:
                min_dob = date(today.year - (max_age + 1), today.month, 28)
            profiles = profiles.filter(date_of_birth__gt=min_dob)
        except (ValueError, TypeError):
            pass

    # Pagination
    paginator = Paginator(profiles, 9)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Context data
    saved_ids = []
    if request.user.is_authenticated:
        saved_ids = list(SavedProfile.objects.filter(
            user=request.user
        ).values_list("saved_user_id", flat=True))

    accepted_requests = ContactRequest.objects.filter(
        status="accepted"
    ).filter(
        Q(sender=request.user) | Q(receiver=request.user)
    )

    accepted_user_ids = {
        r.receiver_id if r.sender_id == request.user.id else r.sender_id
        for r in accepted_requests
    }

    pending_user_ids = set(
        ContactRequest.objects.filter(
            sender=request.user,
            status="pending"
        ).values_list("receiver_id", flat=True)
    )

    context = {
        'page_obj': page_obj,
        'cities': cities,
        'castes': castes,
        'saved_ids': saved_ids,
        'accepted_user_ids': accepted_user_ids,
        'pending_user_ids': pending_user_ids,
        'selected_gender': selected_gender,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'users/includes/profile_grid.html', context)

    return render(request, 'users/profile_list.html', context)

def home(request):
    is_incomplete = False

    if request.user.is_authenticated:
        is_incomplete = not all([
            request.user.date_of_birth,
            request.user.height_cm,
            request.user.city,
            request.user.profile_photo,
        ])

    return render(request, 'users/home.html', {
        'is_incomplete': is_incomplete
    })

@login_required
def edit_profile(request):
    if getattr(request.user, 'is_suspended', False):
        messages.error(request, "Your account has been suspended.")
        return redirect('home')

    if request.method == 'POST':
        if 'profile_photo' in request.FILES:
            upload_key = f"photo_upload_rate_{request.user.id}"
            recent_uploads = cache.get(upload_key, 0)
            if recent_uploads >= 10:
                messages.error(request, "You have reached the photo upload rate limit. Please try again in an hour.")
                return render(request, 'users/edit_profile.html', {'form': UserUpdateForm(instance=request.user)})
            cache.set(upload_key, recent_uploads + 1, timeout=3600)

        old_email = (request.user.email or '').strip().lower()
        old_name = request.user.full_name
        old_gender = request.user.gender

        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)

        if form.is_valid():
            try:
                user = form.save()
                new_email = (user.email or '').strip().lower()
                if old_email != new_email:
                    user.is_email_verified = False
                    user.save(update_fields=['is_email_verified'])
                    try:
                        send_verification_email(request, user)
                        request.session['last_email_verification_sent'] = time.time()
                        messages.info(request, f"Your email address was changed. A verification link has been sent to {user.email}.")
                    except Exception as e:
                        print(f"Email error on update: {e}")

                name_changed = (old_name != user.full_name)
                gender_changed = (old_gender != user.gender)
                photo_changed = bool('profile_photo' in request.FILES or request.POST.get('profile_photo-clear') or request.POST.get('remove_profile_photo'))

                if name_changed or gender_changed or photo_changed:
                    user.is_approved = False
                    user.needs_review = True
                    user.save(update_fields=['is_approved', 'needs_review'])
                    messages.warning(request, "Your profile changes (name, gender, or photo) require re-approval by our moderation team.")
                elif form.has_changed():
                    user.needs_review = True
                    user.save(update_fields=['needs_review'])

                messages.success(request, "Profile updated successfully.")
                return redirect('my_profile')
            except Exception as e:
                err_str = str(e).lower()
                if "permissions" in err_str or "notallowed" in err_str:
                    messages.error(request, "Image upload failed: Your Cloudinary API key has restricted permissions. Please enable 'create/upload' permission on your Cloudinary Access Key.")
                else:
                    messages.error(request, f"Error saving profile: {e}")
    else:
        form = UserUpdateForm(instance=request.user)

    return render(request, 'users/edit_profile.html', {
        'form': form
    })

@login_required
def my_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, 'users/my_profile.html', {
        'profile': profile
    })

def terms_view(request):
    return render(request, 'users/terms.html')

def privacy_view(request):
    return render(request, 'users/privacy.html')

def about_view(request):
    return render(request, 'users/about.html')

@active_member_required
def my_matches(request):
    matches = ContactRequest.objects.filter(
        status='accepted'
    ).filter(
        Q(sender=request.user) | Q(receiver=request.user)
    ).select_related(
        'sender', 'receiver',
        'sender__city', 'receiver__city',
        'sender__subscription', 'receiver__subscription',
        'sender__subscription__plan', 'receiver__subscription__plan'
    )

    matched_users = []

    for m in matches:
        if m.sender == request.user:
            matched_users.append(m.receiver)
        else:
            matched_users.append(m.sender)

    matched_users = [
        u for u in matched_users
        if can_view(request.user, u)
    ]

    return render(request, 'users/my_matches.html', {
        'matched_users': matched_users
    })

@active_member_required
def view_profile(request, user_id):
    profile_user = get_object_or_404(CustomUser, id=user_id)

    if not can_view(request.user, profile_user):
        raise Http404("Profile not found.")

    privacy_ctx = get_profile_privacy_context(request.user, profile_user)

    # pending request object
    pending_request = ContactRequest.objects.filter(
        sender=request.user,
        receiver=profile_user,
        status="pending"
    ).first()

    # saved profiles
    saved_ids = SavedProfile.objects.filter(
        user=request.user
    ).values_list("saved_user_id", flat=True)

    return render(request, "users/view_profile.html", {
        "profile_user": profile_user,
        "pending_request": pending_request,
        "saved_ids": saved_ids,
        **privacy_ctx,
    })

@login_required
def delete_account(request):
    if request.method == "POST":
        password = request.POST.get("password", "")
        if not password or not request.user.check_password(password):
            messages.error(request, "Incorrect password. Account deletion cancelled.")
            return render(request, 'users/delete_account.html')

        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "Your account has been deleted successfully.")
        return redirect('home')

    return render(request, 'users/delete_account.html')

@staff_member_required
def admin_dashboard(request):

    total_users = CustomUser.objects.count()
    approved_users = CustomUser.objects.filter(is_approved=True).count()
    suspended_users = CustomUser.objects.filter(is_suspended=True).count()

    total_requests = ContactRequest.objects.count()
    pending_requests = ContactRequest.objects.filter(status='pending').count()

    total_reports = Report.objects.count()

    top_reported = (
        Report.objects
        .values('reported_user__username')
        .annotate(report_count=Count('id'))
        .order_by('-report_count')[:5]
    )

    pending_users = CustomUser.objects.filter(
        Q(is_approved=False) | Q(is_phone_verified=False)
    ).order_by('-date_joined')[:30]

    context = {
        'total_users': total_users,
        'approved_users': approved_users,
        'suspended_users': suspended_users,
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'total_reports': total_reports,
        'top_reported': top_reported,
        'pending_users': pending_users,
    }

    return render(request, 'admin_dashboard.html', context)


@staff_member_required
def admin_verify_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        user.is_approved = True
        user.is_phone_verified = True
        user.is_email_verified = True
        user.save(update_fields=['is_approved', 'is_phone_verified', 'is_email_verified'])
        messages.success(request, f"User {user.full_name or user.username} has been fully approved and verified (Phone + Email).")
    return redirect('admin_dashboard')


@staff_member_required
def admin_reject_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        user.is_approved = False
        user.is_suspended = True
        user.save(update_fields=['is_approved', 'is_suspended'])
        messages.warning(request, f"User {user.full_name or user.username} has been suspended/rejected.")
    return redirect('admin_dashboard')

def contact_view(request):
    if request.method == "POST":
        honeypot = request.POST.get("website_hp", "").strip()
        if honeypot:
            # Silent discard for bot submissions
            return render(request, "users/contact.html", {"success": True})

        client_ip = get_client_ip(request) or "unknown"
        ip_key = get_ip_network_key(client_ip)
        rate_key = f"contact_rate_{ip_key}"
        current_count = cache.get(rate_key, 0)
        if current_count >= 3:
            messages.error(request, "Too many messages sent from your IP. Please try again later.")
            return render(request, "users/contact.html")

        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        message = request.POST.get("message", "").strip()

        context = {"name": name, "email": email, "message": message}

        if not name or not email or not message:
            messages.error(request, "Please fill in all fields.")
            return render(request, "users/contact.html", context)

        if len(name) > 100:
            messages.error(request, "Name must be 100 characters or fewer.")
            return render(request, "users/contact.html", context)

        if len(email) > 100:
            messages.error(request, "Email must be 100 characters or fewer.")
            return render(request, "users/contact.html", context)

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address.")
            return render(request, "users/contact.html", context)

        if len(message) > 1000:
            messages.error(request, "Message must be 1,000 characters or fewer.")
            return render(request, "users/contact.html", context)

        if cache.get(rate_key) is None:
            cache.set(rate_key, 1, timeout=3600)
        else:
            try:
                cache.incr(rate_key)
            except Exception:
                cache.set(rate_key, current_count + 1, timeout=3600)

        from core.services import send_contact_email
        sent = send_contact_email(name, email, message)

        if sent:
            return render(request, "users/contact.html", {"success": True})
        else:
            messages.error(request, "Unable to send message right now. Please try again later.")
            return redirect("contact_us")

    return render(request, "users/contact.html")



def verify_email(request, token):
    signer = TimestampSigner()

    try:
        unsigned_value = signer.unsign(token, max_age=86400)  # Valid for 24 hours

        # Payload format: "{user_id}:{user_email}"
        if ":" not in str(unsigned_value):
            messages.error(request, "Invalid or unrecognized verification link.")
            return redirect("home")

        user_id_str, token_email = str(unsigned_value).split(":", 1)
        user = CustomUser.objects.get(id=int(user_id_str))

        # Verify that the token corresponds to the user's CURRENT email address
        if (user.email or '').strip().lower() != token_email.strip().lower():
            messages.error(
                request,
                "This verification link was issued for a previous email address. Please request a new verification email."
            )
            return redirect("resend_verification")

        if user.is_email_verified:
            messages.success(request, "Email already verified.")
            return redirect("home")

        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        messages.success(request, "Email verified successfully.")
        return redirect("home")

    except SignatureExpired:
        messages.error(request, "This verification link has expired (valid for 24 hours). Please request a new one.")
        return redirect("resend_verification")

    except (BadSignature, CustomUser.DoesNotExist, ValueError):
        messages.error(request, "Invalid or unrecognized verification link.")
        return redirect("home")
    
@login_required
def resend_verification_email(request):

    if request.user.is_email_verified:
        messages.success(request, "Your email is already verified.")
        return redirect("home")

    last_sent = request.session.get('last_email_verification_sent', 0)
    now = time.time()
    cooldown = 60  # 60-second cooldown to protect free tier quota

    if (now - last_sent) < cooldown:
        wait_seconds = int(cooldown - (now - last_sent))
        messages.warning(
            request,
            f"A verification email was sent recently to {request.user.email}. Please check your inbox and spam folder. You can request another email in {wait_seconds} seconds."
        )
        referer = request.META.get('HTTP_REFERER')
        if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
            return redirect(referer)
        return redirect("home")

    try:
        send_verification_email(request, request.user)
        request.session['last_email_verification_sent'] = now
        messages.success(
            request,
            f"Verification email sent to {request.user.email}. Please check your inbox or spam folder."
        )
    except Exception as e:
        print(f"Error sending verification email: {e}")
        messages.error(
            request,
            "Unable to send verification email right now. Please try again in a moment."
        )

    referer = request.META.get('HTTP_REFERER')
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return redirect(referer)
    return redirect("home")


# ==============================================================================
# PASSWORD RESET VIA EMAIL OTP
# ==============================================================================

from django.core.cache import cache
import hashlib
import hmac
import secrets
from core.services import send_password_reset_code
from .forms import PasswordResetRequestForm, PasswordResetVerifyForm, PasswordResetSetNewForm


def hash_reset_code(email, code):
    """Computes true HMAC-SHA256 digest so raw OTP codes are never stored in cache memory."""
    secret = (getattr(settings, 'SECRET_KEY', None) or 'poorvanchal_default_key').encode('utf-8')
    message = f"{email.lower().strip()}:{code.strip()}".encode('utf-8')
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def mask_email(email):
    if not email or '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        masked = local[0] + '***'
    elif len(local) <= 4:
        masked = local[:2] + '***'
    else:
        masked = local[:3] + '***' + local[-1]
    return f"{masked}@{domain}"


def password_reset_request(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            raw_email = form.cleaned_data['email'].strip().lower()

            hourly_key = f"pwd_reset_hourly_{raw_email}"
            hourly_count = cache.get(hourly_key, 0)
            if hourly_count >= 5:
                messages.warning(
                    request,
                    "Too many password reset requests for this email. Please try again in an hour."
                )
                request.session['pwd_reset_email'] = raw_email
                request.session['pwd_reset_masked_email'] = mask_email(raw_email)
                return redirect('password_reset_verify')

            cooldown_key = f"pwd_reset_cooldown_{raw_email}"
            if cache.get(cooldown_key):
                messages.warning(
                    request,
                    "A verification code was recently requested. Please wait 60 seconds before requesting another code."
                )
                request.session['pwd_reset_email'] = raw_email
                request.session['pwd_reset_masked_email'] = mask_email(raw_email)
                return redirect('password_reset_verify')

            # Prevent user enumeration: Enforce cooldown regardless of whether account exists
            cache.set(cooldown_key, True, timeout=60)
            if cache.get(hourly_key) is None:
                cache.set(hourly_key, 1, timeout=3600)
            else:
                try:
                    cache.incr(hourly_key)
                except Exception:
                    cache.set(hourly_key, hourly_count + 1, timeout=3600)

            user = CustomUser.objects.filter(email__iexact=raw_email).first()
            if user:
                code = f"{secrets.randbelow(1000000):06d}"
                reset_data = {
                    'code_hash': hash_reset_code(raw_email, code),
                    'user_id': user.id,
                    'email': user.email,
                    'attempts': 0,
                    'created_at': time.time(),
                }
                cache.set(f"pwd_reset_data_{raw_email}", reset_data, timeout=900)
                cache.set(f"pwd_reset_attempts_{raw_email}", 0, timeout=900)
                send_password_reset_code(user.email, user.full_name or user.username, code)

            request.session['pwd_reset_email'] = raw_email
            request.session['pwd_reset_masked_email'] = mask_email(raw_email)
            messages.info(
                request,
                f"If an account is associated with {mask_email(raw_email)}, a 6-digit code has been sent."
            )
            return redirect('password_reset_verify')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'users/password_reset_request.html', {'form': form})


def password_reset_verify(request):
    if request.user.is_authenticated:
        return redirect('home')

    email = request.session.get('pwd_reset_email')
    if not email:
        return redirect('password_reset_request')

    masked_email = request.session.get('pwd_reset_masked_email', mask_email(email))
    cooldown_key = f"pwd_reset_cooldown_{email}"
    can_resend = not bool(cache.get(cooldown_key))

    if request.method == 'POST':
        action = request.POST.get('action', 'verify')

        if action == 'resend':
            hourly_key = f"pwd_reset_hourly_{email}"
            hourly_count = cache.get(hourly_key, 0)
            if hourly_count >= 5:
                messages.warning(
                    request,
                    "Too many password reset requests for this email. Please try again in an hour."
                )
                return redirect('password_reset_verify')

            if not can_resend:
                messages.warning(request, "Please wait a moment before requesting another code.")
                return redirect('password_reset_verify')

            cache.set(cooldown_key, True, timeout=60)
            if cache.get(hourly_key) is None:
                cache.set(hourly_key, 1, timeout=3600)
            else:
                try:
                    cache.incr(hourly_key)
                except Exception:
                    cache.set(hourly_key, hourly_count + 1, timeout=3600)

            user = CustomUser.objects.filter(email__iexact=email).first()
            if user:
                code = f"{secrets.randbelow(1000000):06d}"
                reset_data = {
                    'code_hash': hash_reset_code(email, code),
                    'user_id': user.id,
                    'email': user.email,
                    'attempts': 0,
                    'created_at': time.time(),
                }
                cache.set(f"pwd_reset_data_{email}", reset_data, timeout=900)
                cache.set(f"pwd_reset_attempts_{email}", 0, timeout=900)
                send_password_reset_code(user.email, user.full_name or user.username, code)

            messages.success(request, f"If an account is associated with {masked_email}, a fresh code was sent.")
            return redirect('password_reset_verify')

        form = PasswordResetVerifyForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data['code']
            cached_data = cache.get(f"pwd_reset_data_{email}")

            if not cached_data:
                messages.error(request, "Your verification code has expired. Please request a new code.")
                return redirect('password_reset_request')

            attempts_key = f"pwd_reset_attempts_{email}"
            current_attempts = cache.get(attempts_key, 0)
            if current_attempts >= 5:
                cache.delete(f"pwd_reset_data_{email}")
                cache.delete(attempts_key)
                messages.error(request, "Too many incorrect attempts. Please request a new code.")
                return redirect('password_reset_request')

            entered_hash = hash_reset_code(email, entered_code)
            is_valid_code = False
            if 'code_hash' in cached_data:
                is_valid_code = secrets.compare_digest(cached_data['code_hash'], entered_hash)
            elif 'code' in cached_data:
                is_valid_code = secrets.compare_digest(cached_data['code'], entered_code)

            if not is_valid_code:
                try:
                    new_attempts = cache.incr(attempts_key)
                except Exception:
                    new_attempts = current_attempts + 1
                    cache.set(attempts_key, new_attempts, timeout=900)

                if new_attempts >= 5:
                    cache.delete(f"pwd_reset_data_{email}")
                    cache.delete(attempts_key)
                    messages.error(request, "Too many incorrect attempts. Please request a new code.")
                    return redirect('password_reset_request')

                attempts_left = 5 - new_attempts
                messages.error(request, f"Incorrect verification code. {attempts_left} attempt(s) remaining.")
                return render(request, 'users/password_reset_verify.html', {
                    'form': form,
                    'masked_email': masked_email,
                    'can_resend': can_resend
                })

            cache.delete(f"pwd_reset_data_{email}")
            cache.delete(attempts_key)
            request.session['pwd_reset_verified_user_id'] = cached_data['user_id']
            request.session['pwd_reset_verified_time'] = time.time()
            return redirect('password_reset_confirm')
    else:
        form = PasswordResetVerifyForm()

    return render(request, 'users/password_reset_verify.html', {
        'form': form,
        'masked_email': masked_email,
        'can_resend': can_resend
    })



def password_reset_confirm(request):
    if request.user.is_authenticated:
        return redirect('home')

    user_id = request.session.get('pwd_reset_verified_user_id')
    verified_time = request.session.get('pwd_reset_verified_time')

    if not user_id or not verified_time:
        messages.error(request, "Session expired. Please request a new verification code.")
        return redirect('password_reset_request')

    if time.time() - verified_time > 900:
        for k in ['pwd_reset_verified_user_id', 'pwd_reset_verified_time', 'pwd_reset_email', 'pwd_reset_masked_email']:
            request.session.pop(k, None)
        messages.error(request, "Your password reset session has expired. Please try again.")
        return redirect('password_reset_request')

    user = get_object_or_404(CustomUser, pk=user_id)

    if request.method == 'POST':
        form = PasswordResetSetNewForm(request.POST, user=user)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            user.set_password(new_password)
            user.save()

            for k in ['pwd_reset_verified_user_id', 'pwd_reset_verified_time', 'pwd_reset_email', 'pwd_reset_masked_email']:
                request.session.pop(k, None)

            messages.success(request, "Your password has been reset successfully! Please log in with your new password.")
            return redirect('login')
    else:
        form = PasswordResetSetNewForm(user=user)

    return render(request, 'users/password_reset_confirm.html', {
        'form': form,
        'user_name': user.full_name or user.username
    })



