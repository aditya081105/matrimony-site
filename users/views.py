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

from django.contrib.admin.views.decorators import staff_member_required
from .models import CustomUser, Caste, City
from .forms import UserRegisterForm, ProfileForm, UserUpdateForm


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Do NOT auto-login
            messages.success(
                request,
                "Registration successful. Your account is pending admin approval."
            )

            return redirect('login')
    else:
        form = UserRegisterForm()

    return render(request, 'users/register.html', {'form': form})

# Keep your profile_list and contact_view below this...

from django.db.models import Q

@login_required(login_url='login')
def profile_list(request):

    cities = City.objects.all()
    castes = Caste.objects.all()

    if not request.user.is_approved:
        return render(request, 'users/pending_approval.html')
    
    profiles = CustomUser.objects.select_related('profile').filter(
        is_active=True,
        is_approved=True,
        date_of_birth__isnull=False,
        height_cm__isnull=False,
        profile__city_hometown__isnull=False,
        profile__profile_photo__isnull=False,
    ).exclude(id=request.user.id)

    if not request.GET.get('gender') and request.user.gender:
        opposite = 'F' if request.user.gender == 'M' else 'M'
        profiles = profiles.filter(gender=opposite)
    

        
    # -------- FILTERING --------

    gender = request.GET.get('gender')
    caste = request.GET.get('caste')
    city = request.GET.get('city')
    min_height = request.GET.get('min_height')
    max_height = request.GET.get('max_height')
    min_age = request.GET.get('min_age')
    max_age = request.GET.get('max_age')

    if gender:
        profiles = profiles.filter(gender=gender)

    if caste:
        profiles = profiles.filter(
            caste_community__id=caste
        )

    if city:
        profiles = profiles.filter(
            profile__city_hometown__id=city
        )

    if min_height:
        profiles = profiles.filter(height_cm__gte=min_height)

    if max_height:
        profiles = profiles.filter(height_cm__lte=max_height)

    today = date.today()

    if min_age:
        max_dob = date(today.year - int(min_age), today.month, today.day)
        profiles = profiles.filter(date_of_birth__lte=max_dob)

    if max_age:
        min_dob = date(today.year - int(max_age), today.month, today.day)
        profiles = profiles.filter(date_of_birth__gte=min_dob)

    # Accepted (either direction)
    accepted_requests = ContactRequest.objects.filter(
        status='accepted'
    ).filter(
        Q(sender=request.user) | Q(receiver=request.user)
    )

    accepted_user_ids = {
        req.receiver_id if req.sender_id == request.user.id else req.sender_id
        for req in accepted_requests
    }

    pending_user_ids = set(
        ContactRequest.objects.filter(
            sender=request.user,
            status='pending'
        ).values_list('receiver_id', flat=True)
    )

    blocked_by_me = Block.objects.filter(
    blocker=request.user
    ).values_list('blocked_id', flat=True)

    blocked_me = Block.objects.filter(
        blocked=request.user
    ).values_list('blocker_id', flat=True)

    profiles = profiles.exclude(id__in=blocked_by_me)
    profiles = profiles.exclude(id__in=blocked_me)

    # PAGINATION (THIS WAS MISSING)
    paginator = Paginator(profiles, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    saved_ids = SavedProfile.objects.filter(
        user=request.user
    ).values_list("saved_user_id", flat=True)

    return render(request, 'users/profile_list.html', {
        'page_obj': page_obj,
        'cities': cities,
        'castes': castes,
        'accepted_user_ids': accepted_user_ids,
        'pending_user_ids': pending_user_ids,
        "saved_ids": saved_ids,
    })

def contact_view(request):
    return render(request, 'users/contact.html')

def home(request):
    is_incomplete = False

    if request.user.is_authenticated:
        if hasattr(request.user, "profile"):
            if not request.user.profile.is_complete:
                is_incomplete = True

    return render(request, 'users/home.html', {
        'is_incomplete': is_incomplete
    })

@login_required
def edit_profile(request):
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully")
            return redirect('my_profile')
    else:
        user_form = UserUpdateForm(instance=user)
        profile_form = ProfileForm(instance=profile)

    return render(request, 'users/edit_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
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
