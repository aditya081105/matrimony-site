from django.db.models import QuerySet, Q
from django.contrib.auth import get_user_model
from communications.models import Block, ContactRequest

User = get_user_model()


def visible_profiles(viewer) -> QuerySet:
    """
    Returns a QuerySet of user profiles that the given viewer is permitted to see
    in matchmaking lists, search results, and recommendations.

    Rules:
    1. If viewer is unauthenticated, returns none.
    2. If viewer is staff or superuser:
       - Returns all members excluding self and other staff/superusers (for member browsing/moderation).
    3. If viewer is a regular member:
       - Must exclude self.
       - Must exclude staff/superusers.
       - Must exclude inactive, unapproved, and suspended accounts.
       - Must exclude any user who has blocked the viewer, or whom the viewer has blocked.
    """
    if not viewer or not viewer.is_authenticated:
        return User.objects.none()

    is_viewer_admin = bool(viewer.is_staff or viewer.is_superuser)

    if is_viewer_admin:
        return User.objects.exclude(
            id=viewer.id
        ).exclude(
            is_staff=True
        ).exclude(
            is_superuser=True
        )

    blocked_by_me = Block.objects.filter(blocker=viewer).values_list("blocked_id", flat=True)
    blocked_me = Block.objects.filter(blocked=viewer).values_list("blocker_id", flat=True)
    blocked_ids = set(blocked_by_me) | set(blocked_me)

    return User.objects.filter(
        is_active=True,
        is_approved=True,
        is_suspended=False
    ).exclude(
        id__in=blocked_ids
    ).exclude(
        id=viewer.id
    ).exclude(
        is_staff=True
    ).exclude(
        is_superuser=True
    )


def can_view(viewer, target) -> bool:
    """
    Returns True if `viewer` is permitted to view `target`'s profile page.
    Returns False otherwise.

    Rules:
    1. If target is None, returns False.
    2. Viewer can always view their own profile.
    3. Admins/staff can view any target account for moderation purposes.
    4. Target admin/staff accounts are 404/hidden from non-admin viewers.
    5. Inactive, unapproved, or suspended accounts are hidden from non-admin viewers.
    6. Mutual blocks: If viewer blocked target or target blocked viewer, access is blocked.
    """
    if target is None:
        return False

    if not viewer or not viewer.is_authenticated:
        return False

    is_viewer_admin = bool(viewer.is_staff or viewer.is_superuser)
    is_target_admin = bool(target.is_staff or target.is_superuser)

    # Admin/staff can view any account
    if is_viewer_admin:
        return True

    # Non-staff cannot view admin/staff profiles
    if is_target_admin:
        return False

    # Viewing self is always permitted
    if viewer.id == target.id:
        return True

    # Inactive profiles unavailable to non-staff
    if not target.is_active:
        return False

    # Unapproved profiles unavailable to other non-staff
    if not target.is_approved:
        return False

    # Suspended profiles unavailable to non-staff
    if target.is_suspended:
        return False

    # Blocked profiles unavailable in either direction
    if (
        Block.objects.filter(blocker=target, blocked=viewer).exists()
        or Block.objects.filter(blocker=viewer, blocked=target).exists()
    ):
        return False

    return True


def get_profile_privacy_context(viewer, target) -> dict:
    """
    Computes privacy permissions for displaying target's profile to viewer.

    Returns a dictionary containing:
    - is_matched: bool (whether there is an accepted contact request between viewer and target)
    - is_allowed: bool (whether full details including parental names, exact DOB, and contact details may be shown)
    - is_viewer_admin: bool (whether viewer is staff/superuser)
    """
    is_viewer_admin = bool(viewer.is_staff or viewer.is_superuser) if viewer and viewer.is_authenticated else False
    is_self = bool(viewer and viewer.is_authenticated and viewer.id == target.id)

    is_matched = False
    if viewer and viewer.is_authenticated and target and not is_self:
        is_matched = ContactRequest.objects.filter(
            status="accepted"
        ).filter(
            Q(sender=viewer, receiver=target) |
            Q(sender=target, receiver=viewer)
        ).exists()

    is_allowed = is_matched or is_viewer_admin or is_self

    return {
        "is_matched": is_matched,
        "is_allowed": is_allowed,
        "is_viewer_admin": is_viewer_admin,
    }
