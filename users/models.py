# Create your models here.

from django.db.models.signals import post_save
from django.dispatch import receiver

from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # This is the "Base" user (Username/Password)
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]
    
    full_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone_number = models.CharField(max_length=15)
    
    # Specifics for your hometown bureau
    caste_community = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    occupation = models.CharField(max_length=100, help_text="e.g. Software Engineer, Farmer", blank=True)
    height_cm = models.PositiveIntegerField(null=True, blank=True)

    
    # THE PAYWALL SWITCH
    is_paid = models.BooleanField(default=False)
    
    # Language Preference (English/Hindi)
    language_pref = models.CharField(max_length=10, default='en')

    def __str__(self):
        return f"{self.username} - {self.full_name}"

class Profile(models.Model):
    # This links the Profile to a specific User. 
    # If the User is deleted, the Profile is deleted (on_delete=models.CASCADE)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    
    # Bio Data Fields
    bio = models.TextField(max_length=500, blank=True)
    education = models.CharField(max_length=100, blank=True)
    father_name = models.CharField(max_length=100, blank=True)
    mother_name = models.CharField(max_length=100, blank=True)
    city_hometown = models.CharField(max_length=100, blank=True)
    
    # Photos (We will handle the actual 'storage' part later)
    profile_photo = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    @property
    def is_complete(self):
        return all([
            self.father_name,
            self.city_hometown,
            self.bio
        ])

    def __str__(self):
        return f"Profile of {self.user.full_name}"

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class Subscription(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    plan_type = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.user.username} Subscription"