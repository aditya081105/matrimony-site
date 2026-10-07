from django.contrib import admin
from .models import Plan, PaymentOrder


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'price', 'duration_days', 'badge_label', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'plan', 'amount', 'utr_number', 'status', 'created_at', 'verified_at')
    list_filter = ('status', 'created_at', 'plan')
    search_fields = ('user__username', 'user__full_name', 'utr_number', 'id')
    readonly_fields = ('created_at', 'verified_at')
    actions = ['approve_and_activate_subscription', 'reject_payment']

    @admin.action(description="Approve Selected Orders & Activate Subscriptions")
    def approve_and_activate_subscription(self, request, queryset):
        count = 0
        for order in queryset:
            if order.status != 'completed':
                order.activate_subscription()
                count += 1
        self.message_user(request, f"Successfully approved {count} payment order(s) and activated subscriptions.")

    @admin.action(description="Reject Selected Orders")
    def reject_payment(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f"Marked {updated} payment order(s) as rejected.")
