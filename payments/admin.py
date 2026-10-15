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
        if change and obj.pk:
            old_obj = PaymentOrder.objects.filter(pk=obj.pk).first()
            old_status = old_obj.status if old_obj else None
            status_changed = bool(form.changed_data and 'status' in form.changed_data)

            if status_changed and old_status:
                new_status = obj.status
                obj.status = old_status
                super().save_model(request, obj, form, change)
                obj.status = new_status
                if new_status == 'completed' and old_status != 'completed':
                    obj.approve()
                elif new_status == 'rejected' and old_status != 'rejected':
                    obj.reject()
                else:
                    obj.save(update_fields=['status'])
            else:
                super().save_model(request, obj, form, change)
        else:
            target_status = obj.status
            obj.status = 'pending'
            super().save_model(request, obj, form, change)
            if target_status == 'completed':
                obj.approve()
            elif target_status == 'rejected':
                obj.reject()

    @admin.action(description="Approve Selected Orders & Activate Subscriptions")
    def approve_and_activate_subscription(self, request, queryset):
        count = 0
        for order in queryset:
            if order.status != 'completed':
                order.approve()
                count += 1
        self.message_user(request, f"Successfully approved {count} payment order(s) and activated subscriptions.")

    @admin.action(description="Reject Selected Orders & Revoke Subscriptions")
    def reject_payment_and_revoke(self, request, queryset):
        count = 0
        for order in queryset:
            if order.status != 'rejected':
                order.reject()
                count += 1
        self.message_user(request, f"Marked {count} payment order(s) as rejected and updated active access.")
