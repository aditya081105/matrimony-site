from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from users.models import CustomUser
from communications.models import Block


@login_required
def search_view(request):
    query = request.GET.get('q', '').strip()
    profiles = CustomUser.objects.none()

    if query:
        blocked_by_me = Block.objects.filter(blocker=request.user).values_list("blocked_id", flat=True)
        blocked_me = Block.objects.filter(blocked=request.user).values_list("blocker_id", flat=True)
        blocked_ids = set(blocked_by_me) | set(blocked_me)

        # Search across full name, occupation, city, bio, and caste
        profiles = CustomUser.objects.filter(
            is_active=True,
            is_approved=True,
            is_suspended=False
        ).exclude(
            id__in=blocked_ids
        ).exclude(
            id=request.user.id
        ).filter(
            Q(full_name__icontains=query) |
            Q(occupation__icontains=query) |
            Q(city__name__icontains=query) |
            Q(caste_community__name__icontains=query) |
            Q(bio__icontains=query)
        ).select_related('city', 'caste_community', 'subscription', 'subscription__plan').distinct()

    return render(request, 'search/search_results.html', {
        'query': query,
        'profiles': profiles,
    })
