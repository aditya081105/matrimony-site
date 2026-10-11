from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q, Case, When, Value, IntegerField
from django.utils import timezone
from users.models import CustomUser
from communications.models import Block


@login_required
def search_view(request):
    query = request.GET.get('q', '').strip()
    profiles = CustomUser.objects.none()

    if query:
        is_admin = bool(request.user.is_staff or request.user.is_superuser)

        if is_admin:
            base_qs = CustomUser.objects.exclude(
                id=request.user.id
            ).exclude(
                is_staff=True
            ).exclude(
                is_superuser=True
            )
        else:
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
            ).exclude(
                is_staff=True
            ).exclude(
                is_superuser=True
            )

        now = timezone.now()
        active_sub_filter = Q(subscription__is_active=True) & (
            Q(subscription__expires_at__isnull=True) | Q(subscription__expires_at__gt=now)
        )

        tier_case = Case(
            When(active_sub_filter, subscription__plan__code='diamond', then=Value(3)),
            When(active_sub_filter, subscription__plan__code='gold', then=Value(2)),
            When(active_sub_filter, subscription__plan__code='silver', then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        )

        if connection.vendor == 'postgresql':
            from django.contrib.postgres.search import TrigramSimilarity
            profiles = base_qs.annotate(
                similarity=TrigramSimilarity('full_name', query),
                tier_weight=tier_case
            ).filter(
                Q(full_name__trigram_similar=query) |
                Q(occupation__trigram_similar=query) |
                Q(full_name__icontains=query) |
                Q(occupation__icontains=query) |
                Q(city__name__icontains=query) |
                Q(caste__icontains=query) |
                Q(sub_caste__icontains=query) |
                Q(bio__icontains=query)
            ).select_related(
                'profile', 'city', 'caste_community', 'subscription', 'subscription__plan'
            ).order_by('-tier_weight', '-similarity', '-date_joined').distinct()
        else:
            profiles = base_qs.annotate(
                tier_weight=tier_case
            ).filter(
                Q(full_name__icontains=query) |
                Q(occupation__icontains=query) |
                Q(city__name__icontains=query) |
                Q(caste__icontains=query) |
                Q(sub_caste__icontains=query) |
                Q(caste_community__name__icontains=query) |
                Q(bio__icontains=query)
            ).select_related(
                'profile', 'city', 'caste_community', 'subscription', 'subscription__plan'
            ).order_by('-tier_weight', '-date_joined').distinct()

    paginator = Paginator(profiles, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'search/search_results.html', {
        'query': query,
        'page_obj': page_obj,
        'profiles': page_obj,
    })
