# Register your models here.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    # This adds your custom fields to the "User Change" page
    fieldsets = UserAdmin.fieldsets + (
        ('Hometown Bureau Info', {'fields': ('full_name', 'is_paid', 'caste_community', 'occupation', 'height_feet')}),
    )
    
    # This shows the fields in the main list of users
    list_display = ['username', 'full_name', 'is_paid', 'is_staff']
    list_editable = ['is_paid'] # This lets you uncheck from the list!

admin.site.register(CustomUser, CustomUserAdmin)
