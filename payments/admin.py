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
    actions = ['approve_and_activate_subscription', 'reject_payment_and_revoke']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.status == 'completed':
            obj.activate_subscription()
        elif obj.status in ('rejected', 'superseded'):
            if hasattr(obj.user, 'subscription'):
                sub = obj.user.subscription
                if sub.active_order_id == obj.id or sub.active_order == obj:
                    other = PaymentOrder.objects.filter(
                        user=obj.user,
                        status='completed'
                    ).exclude(id=obj.id).order_by('-verified_at', '-created_at').first()
                    if other:
                        other.activate_subscription()
                    else:
                        sub.reset_to_free()

    @admin.action(description="Approve Selected Orders & Activate Subscriptions")
    def approve_and_activate_subscription(self, request, queryset):
        count = 0
        for order in queryset:
            order.activate_subscription()
            count += 1
        self.message_user(request, f"Successfully approved {count} payment order(s) and activated subscriptions.")

    @admin.action(description="Reject Selected Orders & Revoke Subscriptions")
    def reject_payment_and_revoke(self, request, queryset):
        count = 0
        for order in queryset:
            order.status = 'rejected'
            order.save()
            if hasattr(order.user, 'subscription'):
                sub = order.user.subscription
                if sub.active_order_id == order.id or sub.active_order == order:
                    other = PaymentOrder.objects.filter(
                        user=order.user,
                        status='completed'
                    ).exclude(id=order.id).order_by('-verified_at', '-created_at').first()
                    if other:
                        other.activate_subscription()
                    else:
                        sub.reset_to_free()
            count += 1
        self.message_user(request, f"Marked {count} payment order(s) as rejected and updated active access.")
