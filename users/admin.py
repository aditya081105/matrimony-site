# Register your models here.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Profile, Caste, City

@admin.action(description="Approve selected users")
def approve_users(modeladmin, request, queryset):
    queryset.update(is_approved=True)

@admin.action(description="Mark selected users as email verified")
def verify_users(modeladmin, request, queryset):
    queryset.update(is_email_verified=True)

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'full_name', 'is_approved', 'is_staff', 'is_email_verified')
    list_filter = ('is_email_verified', 'is_approved', 'is_staff')
    actions = [approve_users, verify_users]
    fieldsets = UserAdmin.fieldsets + (
        ("Approval", {"fields": ("is_approved", "is_email_verified",)}),
    )


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Profile)

admin.site.register(Caste)
admin.site.register(City)
