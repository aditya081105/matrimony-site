# Register your models here.

from django.contrib import admin
from .models import Report, Block, ActivityLog

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'reported_user', 'created_at')
    search_fields = ('reporter__username', 'reported_user__username')
    list_filter = ('created_at',)

@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('blocker', 'blocked', 'created_at')

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'target_user', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'target_user__username')