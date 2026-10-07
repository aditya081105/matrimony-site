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
        ('completed', 'Verified & Active'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
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

    def __str__(self):
        return f"Order #{self.id} - {self.user.username} - {self.plan.name} (₹{self.amount}) [{self.status}]"

    def activate_subscription(self):
        """Activates or extends user subscription upon payment verification."""
        from users.models import Subscription
        now = timezone.now()
        sub, _ = Subscription.objects.get_or_create(user=self.user)

        # Extend previous end date only if renewing the exact same plan; otherwise start fresh from today
        if sub.is_active and sub.plan_type == self.plan.name and sub.expires_at and sub.expires_at > now:
            sub.expires_at = sub.expires_at + timedelta(days=self.plan.duration_days)
        else:
            sub.expires_at = now + timedelta(days=self.plan.duration_days)

        sub.is_active = True
        sub.plan_type = self.plan.name
        sub.save()

        self.status = 'completed'
        self.verified_at = now
        self.save()
