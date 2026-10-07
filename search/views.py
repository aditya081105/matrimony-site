from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
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

        base_qs = CustomUser.objects.filter(
            is_active=True,
            is_approved=True,
            is_suspended=False
        ).exclude(
            id__in=blocked_ids
        ).exclude(
            id=request.user.id
        )

        # On PostgreSQL: Leverage Full-Text Search with SearchVector and SearchRank
        if connection.vendor == 'postgresql':
            try:
                from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
                vector = (
                    SearchVector('full_name', weight='A') +
                    SearchVector('occupation', weight='B') +
                    SearchVector('caste', weight='B') +
                    SearchVector('sub_caste', weight='C') +
                    SearchVector('bio', weight='D')
                )
                search_query = SearchQuery(query)
                profiles = base_qs.annotate(
                    rank=SearchRank(vector, search_query)
                ).filter(
                    Q(rank__gte=0.05) |
                    Q(full_name__icontains=query) |
                    Q(city__name__icontains=query)
                ).select_related(
                    'profile', 'city', 'caste_community', 'subscription', 'subscription__plan'
                ).order_by('-rank', '-date_joined').distinct()
            except Exception:
                profiles = base_qs.filter(
                    Q(full_name__icontains=query) |
                    Q(occupation__icontains=query) |
                    Q(city__name__icontains=query) |
                    Q(caste__icontains=query) |
                    Q(sub_caste__icontains=query) |
                    Q(caste_community__name__icontains=query) |
                    Q(bio__icontains=query)
                ).select_related(
                    'profile', 'city', 'caste_community', 'subscription', 'subscription__plan'
                ).order_by('-date_joined').distinct()
        else:
            profiles = base_qs.filter(
                Q(full_name__icontains=query) |
                Q(occupation__icontains=query) |
                Q(city__name__icontains=query) |
                Q(caste__icontains=query) |
                Q(sub_caste__icontains=query) |
                Q(caste_community__name__icontains=query) |
                Q(bio__icontains=query)
            ).select_related(
                'profile', 'city', 'caste_community', 'subscription', 'subscription__plan'
            ).order_by('-date_joined').distinct()

    paginator = Paginator(profiles, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'search/search_results.html', {
        'query': query,
        'page_obj': page_obj,
        'profiles': page_obj,
    })
