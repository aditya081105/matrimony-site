# Create your views here.

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from .models import CustomUser
from .forms import UserRegisterForm, ProfileForm
from communications.models import ContactRequest

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Auto login after register
            return redirect('edit_profile')  # We will create this next
    else:
        form = UserRegisterForm()

    return render(request, 'users/register.html', {'form': form})

# Keep your profile_list and contact_view below this...

@login_required
def profile_list(request):

    profiles = CustomUser.objects.select_related('profile').filter(
        is_active=True
    ).exclude(
        id=request.user.id
    )

    # Get accepted requests involving current user
    accepted_requests = ContactRequest.objects.filter(
        status='accepted'
    ).filter(
        sender=request.user
    ) | ContactRequest.objects.filter(
        status='accepted',
        receiver=request.user
    )

    accepted_user_ids = set()

    for req in accepted_requests:
        if req.sender == request.user:
            accepted_user_ids.add(req.receiver.id)
        else:
            accepted_user_ids.add(req.sender.id)

    paginator = Paginator(profiles, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'users/profile_list.html', {
        'page_obj': page_obj,
        'accepted_user_ids': accepted_user_ids
    })

def contact_view(request):
    return render(request, 'users/contact.html')

def home(request):
    return render(request, 'users/home.html')

from .forms import UserUpdateForm, ProfileForm

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
    return render(request, 'users/my_profile.html', {'profile': profile})
