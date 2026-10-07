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
    queryset.update(is_approved=True)


@admin.action(description="Mark selected users as email verified")
def verify_users(modeladmin, request, queryset):
    queryset.update(is_email_verified=True)


@admin.action(description="Mark selected users as phone verified")
def verify_phone_users(modeladmin, request, queryset):
    queryset.update(is_phone_verified=True)


@admin.action(description="Fully Approve & Verify (Profile + Phone + Email)")
def fully_verify_users(modeladmin, request, queryset):
    queryset.update(is_approved=True, is_phone_verified=True, is_email_verified=True)


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'full_name', 'phone_number', 'caste', 'sub_caste', 'is_approved', 'is_phone_verified', 'is_email_verified', 'is_premium', 'is_staff')
    list_filter = ('is_approved', 'is_phone_verified', 'is_email_verified', 'is_staff')
    search_fields = ('username', 'full_name', 'email', 'phone_number', 'caste', 'sub_caste')
    actions = [approve_users, verify_phone_users, verify_users, fully_verify_users]
    inlines = [SubscriptionInline]
    fieldsets = UserAdmin.fieldsets + (
        ("Approval & Verification", {"fields": ("is_approved", "is_phone_verified", "is_email_verified")}),
        ("Community & Profile Details", {"fields": ("caste", "sub_caste", "caste_community", "city", "occupation", "height_cm", "date_of_birth")}),
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
