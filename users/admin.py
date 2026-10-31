from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from datetime import timedelta
from .models import CustomUser, Profile, Caste, City, Subscription


class SubscriptionInline(admin.StackedInline):
    model = Subscription
    can_delete = False
    verbose_name_plural = 'Membership Subscription'
    fk_name = 'user'
    extra = 0


@admin.action(description="Approve selected users")
def approve_users(modeladmin, request, queryset):
    queryset.update(is_approved=True, needs_review=False)


@admin.action(description="Mark selected users as email verified")
def verify_users(modeladmin, request, queryset):
    queryset.update(is_email_verified=True)


@admin.action(description="Mark selected users as phone verified")
def verify_phone_users(modeladmin, request, queryset):
    queryset.update(is_phone_verified=True)


@admin.action(description="Fully Approve & Verify (Profile + Phone + Email)")
def fully_verify_users(modeladmin, request, queryset):
    queryset.update(is_approved=True, is_phone_verified=True, is_email_verified=True, needs_review=False)


@admin.action(description="Mark profile edits as reviewed")
def mark_reviewed(modeladmin, request, queryset):
    queryset.update(needs_review=False)


@admin.action(description="Unsuspend selected users (restore access)")
def unsuspend_users(modeladmin, request, queryset):
    user_ids = list(queryset.values_list('id', flat=True))
    try:
        from communications.models import Report
        Report.objects.filter(reported_user_id__in=user_ids).delete()
    except Exception:
        pass
    queryset.update(is_suspended=False, is_approved=True, suspended_until=None, suspension_reason="")


@admin.action(description="Suspend selected users for 7 days")
def suspend_7_days(modeladmin, request, queryset):
    queryset.update(is_suspended=True, is_approved=False, suspended_until=timezone.now() + timedelta(days=7))


@admin.action(description="Suspend selected users for 30 days")
def suspend_30_days(modeladmin, request, queryset):
    queryset.update(is_suspended=True, is_approved=False, suspended_until=timezone.now() + timedelta(days=30))


@admin.action(description="Suspend selected users indefinitely")
def suspend_indefinite(modeladmin, request, queryset):
    queryset.update(is_suspended=True, is_approved=False, suspended_until=None)


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'full_name', 'phone_number', 'is_approved', 'is_suspended', 'suspended_until', 'needs_review', 'is_phone_verified', 'is_email_verified', 'is_staff')
    list_filter = ('is_suspended', 'is_approved', 'needs_review', 'is_phone_verified', 'is_email_verified', 'is_staff')
    search_fields = ('username', 'full_name', 'email', 'phone_number', 'caste', 'sub_caste')
    actions = [
        approve_users,
        unsuspend_users,
        suspend_7_days,
        suspend_30_days,
        suspend_indefinite,
        verify_phone_users,
        verify_users,
        fully_verify_users,
        mark_reviewed,
    ]
    inlines = [SubscriptionInline]
    fieldsets = UserAdmin.fieldsets + (
        ("Approval & Suspension", {"fields": ("is_approved", "is_suspended", "suspended_until", "suspension_reason", "needs_review", "is_phone_verified", "is_email_verified")}),
        ("Community & Profile Details", {"fields": ("caste", "sub_caste", "caste_community", "city", "education", "occupation", "height_cm", "date_of_birth")}),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan_type', 'is_active', 'expires_at', 'is_valid')
    list_filter = ('is_active', 'plan_type')
    search_fields = ('user__username', 'user__full_name')
    actions = ['reset_to_free', 'activate_30_days']

    @admin.action(description="Reset Selected Subscriptions to Free (Cancel)")
    def reset_to_free(self, request, queryset):
        for sub in queryset:
            sub.reset_to_free()
        self.message_user(request, f"Successfully reset {queryset.count()} subscription(s) to Free.")

    @admin.action(description="Grant Active Membership (30 Days from today)")
    def activate_30_days(self, request, queryset):
        queryset.update(
            is_active=True,
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.message_user(request, f"Activated 30-day membership for {queryset.count()} user(s).")


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Profile)
admin.site.register(Caste)
admin.site.register(City)
