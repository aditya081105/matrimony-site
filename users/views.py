from datetime import date
from django.db.models import Q, Count
from django.db import models
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.contrib.auth import logout
from communications.models import Block, ContactRequest, ActivityLog, Report, SavedProfile
from django.http import HttpResponse
from django.core.signing import Signer

from django.contrib.admin.views.decorators import staff_member_required
from .models import CustomUser, Caste, City
from .forms import UserRegisterForm, UserUpdateForm
from django.core.mail import send_mail
from django.urls import reverse
import os 

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.is_active = True # Keep them inactive until admin/email check
            user.save()

            try:
                signer = Signer()
                token = signer.sign(user.id)

                verify_link = request.build_absolute_uri(
                    reverse("verify_email", args=[token])
                )
                send_mail(
                    "Verify your account",
                    f"""
                    Welcome to your site.

                    Click the link below to verify your email:

                    {verify_link}

                    If you did not create this account, ignore this email.
                    """,
                    os.getenv("EMAIL_USER"), # Explicitly use the env var
                    [user.email],
                    fail_silently=True, # This is the shield!
                )
            except Exception as e:
                print(f"Email error: {e}") # Log it to Render logs, don't crash

            messages.success(request, "Registration successful. Pending admin approval.")
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})


# Keep your profile_list and contact_view below this...

from django.db.models import Q

@login_required(login_url='login')
def profile_list(request):

    if not request.user.is_approved:
        return render(request, 'users/pending_approval.html')

    if not request.user.is_email_verified:
        return render(request, "users/verify_email_required.html")

    cities = City.objects.all()
    castes = Caste.objects.all()

    profiles = CustomUser.objects.filter(
        is_active=True,
        is_approved=True
    ).exclude(id=request.user.id)

    # Opposite gender by default
    if not request.GET.get('gender') and request.user.gender:
        opposite = 'F' if request.user.gender == 'M' else 'M'
        profiles = profiles.filter(gender=opposite)

    # Apply filters
    if request.GET.get('gender'):
        profiles = profiles.filter(gender=request.GET.get('gender'))
    if request.GET.get('caste'):
        profiles = profiles.filter(caste_community_id=request.GET.get('caste'))
    if request.GET.get('city'):
        profiles = profiles.filter(city_id=request.GET.get('city'))
    if request.GET.get('min_height'):
        profiles = profiles.filter(height_cm__gte=request.GET.get('min_height'))
    if request.GET.get('max_height'):
        profiles = profiles.filter(height_cm__lte=request.GET.get('max_height'))
    if request.GET.get('min_age'):
        min_age = int(request.GET.get('min_age'))
        max_dob = date.today().replace(year=date.today().year - min_age)
        profiles = profiles.filter(date_of_birth__lte=max_dob)
    if request.GET.get('max_age'):
        max_age = int(request.GET.get('max_age'))
        min_dob = date.today().replace(year=date.today().year - max_age)
        profiles = profiles.filter(date_of_birth__gte=min_dob)

    # Pagination
    paginator = Paginator(profiles, 9)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Context data
    saved_ids = []
    if request.user.is_authenticated:
        saved_ids = list(SavedProfile.objects.filter(
            user=request.user
        ).values_list("saved_user_id", flat=True))

    context = {
        'page_obj': page_obj,
        'cities': cities,
        'castes': castes,
        'saved_ids': saved_ids,
        'accepted_user_ids': set(),      # fill later if needed
        'pending_user_ids': set(),       # fill later if needed
    }

    return render(request, 'users/profile_list.html', context)

def contact_view(request):
    return render(request, 'users/contact.html')

def home(request):
    is_incomplete = False
    if request.user.is_authenticated:
        if not request.user.profile_photo:
            is_incomplete = True

    return render(request, 'users/home.html', {
        'is_incomplete': is_incomplete
    })

@login_required
def edit_profile(request):

    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)

        if form.is_valid():
            form.save()
            return redirect('my_profile')
    else:
        form = UserUpdateForm(instance=request.user)

    return render(request, 'users/edit_profile.html', {
        'form': form
    })

@login_required
def my_profile(request):
    profile = request.user.profile
    return render(request, 'users/my_profile.html', {
        'profile': profile
    })

def terms_view(request):
    return render(request, 'users/terms.html')

def privacy_view(request):
    return render(request, 'users/privacy.html')

def about_view(request):
    return render(request, 'users/about.html')

@login_required
def my_matches(request):
    matches = ContactRequest.objects.filter(
        status='accepted'
    ).filter(
        sender=request.user
    ) | ContactRequest.objects.filter(
        status='accepted',
        receiver=request.user
    )

    matched_users = []

    for m in matches:
        if m.sender == request.user:
            matched_users.append(m.receiver)
        else:
            matched_users.append(m.sender)

    return render(request, 'users/my_matches.html', {
        'matched_users': matched_users
    })

@login_required
def view_profile(request, user_id):

    profile_user = get_object_or_404(CustomUser, id=user_id)

    if Block.objects.filter(blocker=profile_user, blocked=request.user).exists():
        return redirect("profile_list")

    # accepted match
    is_allowed = ContactRequest.objects.filter(
        sender=request.user,
        receiver=profile_user,
        status="accepted"
    ).exists() or ContactRequest.objects.filter(
        sender=profile_user,
        receiver=request.user,
        status="accepted"
    ).exists()

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
        "is_allowed": is_allowed,
        "pending_request": pending_request,
        "saved_ids": saved_ids
    })

@login_required
def delete_account(request):

    if request.method == "POST":
        user = request.user
        logout(request)
        user.delete()
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

    context = {
        'total_users': total_users,
        'approved_users': approved_users,
        'suspended_users': suspended_users,
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'total_reports': total_reports,
        'top_reported': top_reported,
    }

    return render(request, 'admin_dashboard.html', context)

def contact_view(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        message = request.POST.get("message")

        send_mail(
            subject=f"Contact Form - {name}",
            message=f"From: {email}\n\n{message}",
            from_email=None,
            recipient_list=["aditya08112005@gmail.com"],
        )

        return render(request, "users/contact.html", {"success": True})

    return render(request, "users/contact.html")

from django.core.signing import Signer, BadSignature

def verify_email(request, token):
    signer = Signer()

    try:
        user_id = signer.unsign(token)
        user = CustomUser.objects.get(id=user_id)

        user.is_email_verified = True
        user.is_active = True
        user.save()

        return HttpResponse("Email verified successfully")

    except BadSignature:
        return HttpResponse("Invalid or expired link")
    
