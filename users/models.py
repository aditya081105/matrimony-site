# Create your models here.

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

from datetime import date
from django.contrib.auth.models import AbstractUser
from django.db import models

class Caste(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class City(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class CustomUser(AbstractUser):

    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]

    full_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)

    phone_number = models.CharField(max_length=13)

    date_of_birth = models.DateField(null=True, blank=True)
    occupation = models.CharField(max_length=100, blank=True)

    height_cm = models.PositiveIntegerField(null=True, blank=True)

    caste_community = models.ForeignKey(
        'Caste',
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    caste = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Caste / Community"
    )

    sub_caste = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Sub-Caste / Gotra"
    )

    # Replaces Profile
    profile_photo = models.ImageField(
        upload_to="profile_pics/",
        null=True,
        blank=True
    )

    city = models.ForeignKey(
        'City',
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    bio = models.TextField(blank=True)
    father_name = models.CharField(max_length=100, blank=True)
    mother_name = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)

    is_approved = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def is_premium(self):
        try:
            return bool(hasattr(self, 'subscription') and self.subscription.is_valid)
        except Exception:
            return False

    @property
    def membership_tier(self):
        try:
            if hasattr(self, 'subscription') and self.subscription.is_valid:
                sub = self.subscription
                if sub.plan and sub.plan.code:
                    return sub.plan.code.lower()
                pt = (sub.plan_type or '').lower()
                if 'silver' in pt:
                    return 'silver'
                elif 'gold' in pt:
                    return 'gold'
                elif 'diamond' in pt:
                    return 'diamond'
                elif pt and pt != 'free':
                    return 'vip'
        except Exception:
            pass
        return None

    @property
    def display_caste(self):
        c = (self.caste or '').strip()
        sc = (self.sub_caste or '').strip()
        if not c and self.caste_community:
            c = str(self.caste_community.name).strip()
        if c and sc:
            return f"{c} ({sc})"
        return c or sc or ""

    class Meta:
        indexes = [
            models.Index(fields=['is_active', 'is_approved', 'is_suspended', 'gender'], name='user_match_idx'),
            models.Index(fields=['city', 'gender'], name='user_city_gender_idx'),
            models.Index(fields=['caste', 'gender'], name='user_caste_gender_idx'),
            models.Index(fields=['-date_joined'], name='user_date_joined_idx'),
        ]

    def __str__(self):
        return self.username

class Profile(models.Model):

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    bio = models.TextField(max_length=500, blank=True)
    education = models.CharField(max_length=100, blank=True)
    father_name = models.CharField(max_length=100, blank=True)
    mother_name = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)

    city_hometown = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    profile_photo = models.ImageField(
        upload_to="profile_pics/",
        blank=True,
        null=True
    )

    @property
    def is_complete(self):
        return all([
            self.user.date_of_birth,
            self.user.height_cm,
            (self.city_hometown or self.user.city),
            (self.profile_photo or self.user.profile_photo)
        ])

    def __str__(self):
        return f"Profile of {self.user.full_name}"
    
    
@receiver(post_save, sender=CustomUser)
def create_or_sync_user_profile(sender, instance, created, **kwargs):
    profile, _ = Profile.objects.get_or_create(user=instance)
    Subscription.objects.get_or_create(user=instance, defaults={'plan_type': 'Free', 'is_active': False})

    # Keep profile synced with user fields
    needs_save = False
    if instance.city and profile.city_hometown_id != instance.city_id:
        profile.city_hometown = instance.city
        needs_save = True
    if instance.father_name and profile.father_name != instance.father_name:
        profile.father_name = instance.father_name
        needs_save = True
    if instance.mother_name and profile.mother_name != instance.mother_name:
        profile.mother_name = instance.mother_name
        needs_save = True
    if instance.address and profile.address != instance.address:
        profile.address = instance.address
        needs_save = True
    if instance.bio and profile.bio != instance.bio:
        profile.bio = instance.bio
        needs_save = True
    if (instance.profile_photo or profile.profile_photo) and profile.profile_photo != instance.profile_photo:
        profile.profile_photo = instance.profile_photo
        needs_save = True
    if needs_save:
        profile.save()


class Subscription(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='subscription')
    is_active = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    plan_type = models.CharField(max_length=50, default='Free', blank=True)
    plan = models.ForeignKey(
        'payments.Plan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions'
    )
    active_order = models.ForeignKey(
        'payments.PaymentOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions'
    )

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at:
            from django.utils import timezone
            if self.expires_at <= timezone.now():
                return False
        return True

    def reset_to_free(self):
        self.is_active = False
        self.plan = None
        self.active_order = None
        self.plan_type = 'Free'
        self.expires_at = None
        self.save()

    def __str__(self):
        status = "Active" if self.is_valid else "Inactive"
        return f"{self.user.username} ({self.plan_type} - {status})"


@receiver([post_save, post_delete], sender=City)
def handle_city_cache_invalidation(sender, **kwargs):
    from core.caching import invalidate_city_cache
    invalidate_city_cache()


@receiver([post_save, post_delete], sender=Caste)
def handle_caste_cache_invalidation(sender, **kwargs):
    from core.caching import invalidate_caste_cache
    invalidate_caste_cache()
    