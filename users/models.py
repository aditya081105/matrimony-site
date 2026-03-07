# Create your models here.

from django.db.models.signals import post_save
from django.dispatch import receiver

from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

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
    # This is the "Base" user (Username/Password)
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]
    
    full_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, db_index=True)
    phone_number = models.CharField(max_length=13)
    gotra = models.CharField(max_length=100, blank=True)
    annual_income = models.PositiveIntegerField(null=True, blank=True)
    
    # Specifics for your hometown bureau
    caste_community = models.ForeignKey(
        Caste,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    date_of_birth = models.DateField(null=True, blank=True)
    occupation = models.CharField(max_length=100, help_text="e.g. Software Engineer, Farmer", blank=True)
    height_cm = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    is_deleted = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False, db_index=True)
    is_profile_complete = models.BooleanField(default=False, db_index=True)
    is_suspended = models.BooleanField(default=False, db_index=True)
    # Language Preference (English/Hindi)
    language_pref = models.CharField(max_length=10, default='en')

    def __str__(self):
        return f"{self.username} - {self.full_name}"

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

    def __str__(self):
        return f"Profile of {self.user.full_name}"
    

    
@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


class Subscription(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    plan_type = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.user.username} Subscription"
    