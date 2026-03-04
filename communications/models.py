# Create your models here.

from django.db import models
from django.conf import settings
from users.models import CustomUser
from django.utils import timezone

class ContactRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_requests'
    )

    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_requests'
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    attempt_count = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender} → {self.receiver} ({self.status})"
    
class Block(models.Model):
    blocker = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='blocks_made')
    blocked = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='blocks_received')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')


class Report(models.Model):
    reporter = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reports_made')
    reported_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reports_received')
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class RequestAttempt(models.Model):
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='sent_attempts'
    )
    receiver = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='received_attempts'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['sender', 'receiver', 'created_at'])
        ]

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('view_profile', 'Viewed Profile'),
        ('send_request', 'Sent Request'),
        ('accept_request', 'Accepted Request'),
        ('reject_request', 'Rejected Request'),
        ('block_user', 'Blocked User'),
        ('report_user', 'Reported User'),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='activities'
    )

    target_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='targeted_activities'
    )

    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user} - {self.action}"
    
class SavedProfile(models.Model):

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="saved_profiles"
    )

    saved_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="saved_by"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "saved_user")

    def __str__(self):
        return f"{self.user} saved {self.saved_user}"