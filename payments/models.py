from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Plan(models.Model):
    PLAN_CODE_CHOICES = [
        ('silver', 'Silver Plan'),
        ('gold', 'Gold Plan'),
        ('diamond', 'Diamond VIP Plan'),
    ]

    code = models.CharField(max_length=20, unique=True, choices=PLAN_CODE_CHOICES)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)
    features = models.TextField(help_text="Newline-separated list of features")
    badge_label = models.CharField(max_length=50, blank=True, help_text="e.g. Most Popular, Best Value")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['price']

    def get_features_list(self):
        return [f.strip() for f in self.features.split('\n') if f.strip()]

    def __str__(self):
        return f"{self.name} - ₹{self.price} ({self.duration_days} days)"


class PaymentOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('completed', 'Active'),
        ('superseded', 'Superseded'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_orders'
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='orders'
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    utr_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="12-digit UPI Transaction / UTR Number"
    )
    payment_method = models.CharField(max_length=50, default='UPI QR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    admin_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    verified_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['utr_number'],
                condition=models.Q(utr_number__isnull=False) & ~models.Q(status='rejected'),
                name='unique_active_utr_order'
            )
        ]

    def __str__(self):
        username = self.user.username if self.user else "Deleted User"
        plan_name = self.plan.name if self.plan else "No Plan"
        return f"Order #{self.id} - {username} - {plan_name} (₹{self.amount}) [{self.status}]"

    def approve(self):
        """
        Approves order and activates/extends user subscription idempotently.
        Guarded with atomic transaction and row-level lock.
        """
        from django.db import transaction
        from users.models import Subscription

        now = timezone.now()
        with transaction.atomic():
            if not self.pk:
                self.save()

            locked_order = PaymentOrder.objects.select_for_update().get(pk=self.pk)
            if locked_order.status == 'completed':
                self.status = 'completed'
                self.verified_at = locked_order.verified_at
                return

            if not self.user:
                locked_order.status = 'completed'
                locked_order.verified_at = now
                locked_order.save(update_fields=['status', 'verified_at'])
                self.status = 'completed'
                self.verified_at = now
                return

            sub, _ = Subscription.objects.select_for_update().get_or_create(user=self.user)

            # Mark all other completed orders for this user as superseded
            PaymentOrder.objects.filter(
                user=self.user,
                status='completed'
            ).exclude(id=self.id).update(status='superseded')

            # Extend previous end date only if renewing the exact same plan with active unexpired subscription
            if sub.is_active and (sub.plan == self.plan or sub.plan_type == self.plan.name) and sub.expires_at and sub.expires_at > now:
                sub.expires_at = sub.expires_at + timedelta(days=self.plan.duration_days)
            else:
                sub.expires_at = now + timedelta(days=self.plan.duration_days)

            sub.is_active = True
            sub.plan = self.plan
            sub.plan_type = self.plan.name
            sub.active_order = locked_order
            sub.save()

            locked_order.status = 'completed'
            locked_order.verified_at = now
            locked_order.save(update_fields=['status', 'verified_at'])

            self.status = 'completed'
            self.verified_at = now

    def reject(self):
        """
        Rejects order and revokes or resets active subscription idempotently.
        Guarded with atomic transaction and row-level lock.
        """
        from django.db import transaction

        with transaction.atomic():
            if not self.pk:
                self.save()

            locked_order = PaymentOrder.objects.select_for_update().get(pk=self.pk)
            if locked_order.status == 'rejected':
                self.status = 'rejected'
                return

            was_completed = (locked_order.status == 'completed')
            locked_order.status = 'rejected'
            locked_order.save(update_fields=['status'])
            self.status = 'rejected'

            if was_completed and self.user and hasattr(self.user, 'subscription'):
                sub = self.user.subscription
                if sub.active_order_id == self.id or sub.active_order == self:
                    other = PaymentOrder.objects.filter(
                        user=self.user,
                        status__in=['completed', 'superseded']
                    ).exclude(id=self.id).order_by('-verified_at', '-created_at').first()
                    if other:
                        other.status = 'superseded'
                        other.approve()
                    else:
                        sub.reset_to_free()

    def activate_subscription(self):
        """Backward-compatible delegation to approve()."""
        return self.approve()


from django.db.models.signals import post_delete
from django.dispatch import receiver


@receiver(post_delete, sender=PaymentOrder)
def handle_payment_order_deleted(sender, instance, **kwargs):
    if instance.user and hasattr(instance.user, 'subscription'):
        sub = instance.user.subscription
        if sub.active_order_id == instance.id or sub.active_order == instance:
            latest_completed = PaymentOrder.objects.filter(
                user=instance.user,
                status__in=['completed', 'superseded']
            ).exclude(id=instance.id).order_by('-verified_at', '-created_at').first()
            if latest_completed:
                latest_completed.status = 'superseded'
                latest_completed.approve()
            else:
                sub.reset_to_free()


@receiver(post_delete, sender=Plan)
def handle_plan_deleted(sender, instance, **kwargs):
    from users.models import Subscription
    subs = Subscription.objects.filter(
        models.Q(plan=instance) | models.Q(plan_type=instance.name)
    )
    for sub in subs:
        latest_completed = PaymentOrder.objects.filter(
            user=sub.user,
            status__in=['completed', 'superseded'],
            plan__isnull=False
        ).exclude(plan=instance).order_by('-verified_at', '-created_at').first()
        if latest_completed:
            latest_completed.status = 'superseded'
            latest_completed.approve()
        else:
            sub.reset_to_free()


@receiver([models.signals.post_save, models.signals.post_delete], sender=Plan)
def handle_plan_cache_invalidation(sender, **kwargs):
    from core.caching import invalidate_plan_cache
    invalidate_plan_cache()


