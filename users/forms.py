import re
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.cache import cache
from core.utils import get_client_ip
from .models import CustomUser, Profile, Caste, City
from .validators import validate_unique_and_legitimate_email, validate_image_file
from datetime import date

# =========================
# REGISTER FORM
# =========================

class UserRegisterForm(UserCreationForm):

    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address'
        })
    )

    full_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    gender = forms.ChoiceField(
        choices=CustomUser.GENDER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    occupation = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    caste = forms.CharField(
        max_length=100,
        required=False,
        label="Caste / Community",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your caste / community',
            'list': 'caste-suggestions'
        })
    )

    sub_caste = forms.CharField(
        max_length=100,
        required=False,
        label="Sub-Caste / Gotra",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter sub-caste or gotra (optional)'
        })
    )

    phone_number = forms.CharField(
        max_length=10,
        min_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10 digit mobile number'
        })
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text=""
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text=""
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        return validate_unique_and_legitimate_email(email)

    def clean_phone_number(self):
        phone = (self.cleaned_data.get('phone_number') or '').strip()

        # Strictly enforce ASCII digits and Indian mobile prefixes (6-9)
        if not re.fullmatch(r"[6-9][0-9]{9}", phone):
            raise forms.ValidationError("Enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.")

        if len(set(phone)) == 1 or phone in ('1234567890', '0123456789'):
            raise forms.ValidationError("Please enter a valid, active mobile number.")

        if CustomUser.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("This mobile number is already registered. Please log in or use a different number.")

        return phone
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')

        today = date.today()

        if dob > today:
            raise forms.ValidationError("Invalid date.")

        age = today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )

        if age < 18:
            raise forms.ValidationError("You must be at least 18 years old.")

        return dob

    class Meta:
        model = CustomUser
        fields = (
            'username',
            'email',
            'full_name',
            'gender',
            'phone_number',
            'date_of_birth',
            'occupation',
            'caste',
            'sub_caste',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'username' in self.fields:
            self.fields['username'].widget.attrs['class'] = 'form-control'
            self.fields['username'].widget.attrs['placeholder'] = 'Username'
        self.fields['full_name'].widget.attrs['placeholder'] = "Full Name"
        self.fields['phone_number'].widget.attrs['placeholder'] = "Phone Number"
        self.fields['password1'].label = "Enter Password"
        self.fields['password2'].label = "Retype Password"


# =========================
# USER UPDATE FORM
# =========================

class UserUpdateForm(forms.ModelForm):

    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address'
        })
    )

    phone_number = forms.CharField(
        max_length=10,
        min_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10 digit mobile number'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        exclude_id = self.instance.pk if self.instance and self.instance.pk else None
        return validate_unique_and_legitimate_email(email, exclude_user_id=exclude_id)

    def clean_phone_number(self):
        phone = (self.cleaned_data.get('phone_number') or '').strip()

        # Strictly enforce ASCII digits and Indian mobile prefixes (6-9)
        if not re.fullmatch(r"[6-9][0-9]{9}", phone):
            raise forms.ValidationError("Enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.")

        if len(set(phone)) == 1 or phone in ('1234567890', '0123456789'):
            raise forms.ValidationError("Please enter a valid, active mobile number.")

        exclude_id = self.instance.pk if self.instance and self.instance.pk else None
        qs = CustomUser.objects.filter(phone_number=phone)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise forms.ValidationError("This mobile number is already registered by another account.")

        return phone

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if not dob:
            return dob

        today = date.today()

        if dob > today:
            raise forms.ValidationError("Invalid date.")

        age = today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )

        if age < 18:
            raise forms.ValidationError("You must be at least 18 years old.")

        return dob

    def clean_height_cm(self):
        height = self.cleaned_data.get("height_cm")
        if height is not None and height <= 0:
            raise forms.ValidationError("Height must be a positive number.")
        return height

    def clean_profile_photo(self):
        if self.data.get('profile_photo-clear') or self.data.get('remove_profile_photo'):
            return False
        photo = self.cleaned_data.get('profile_photo')
        if photo and hasattr(photo, 'file') and 'profile_photo' in self.files:
            photo = validate_image_file(photo, max_size_mb=5)
        return photo

    class Meta:
        model = CustomUser
        fields = [
            'full_name',
            'email',
            'gender',
            'phone_number',
            'date_of_birth',
            'occupation',
            'height_cm',
            'caste',
            'sub_caste',
            'profile_photo',
            'city',
            'bio',
            'father_name',
            'mother_name',
            'address',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'height_cm': forms.NumberInput(attrs={'class': 'form-control'}),
            'caste': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Rajput, Yadav, Brahmin, etc.',
                'list': 'caste-suggestions'
            }),
            'sub_caste': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Chauhan, Gautam, Kashyap, etc.'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'profile_photo':
                existing_classes = field.widget.attrs.get('class', '')
                if 'form-control' not in existing_classes and 'form-select' not in existing_classes:
                    if isinstance(field.widget, forms.Select):
                        field.widget.attrs['class'] = 'form-select'
                    else:
                        field.widget.attrs['class'] = 'form-control'
        if 'bio' in self.fields:
            self.fields['bio'].widget.attrs['rows'] = 3

    def save(self, commit=True):
        is_cleared = bool(self.data.get('profile_photo-clear') or self.data.get('remove_profile_photo'))

        # Track existing photo filename to delete the old file from disk upon replacement or removal
        old_photo_name = None
        if self.instance and self.instance.pk:
            old_photo_name = CustomUser.objects.filter(pk=self.instance.pk).values_list('profile_photo', flat=True).first()

        if is_cleared:
            self.instance.profile_photo = None
        user = super().save(commit=commit)
        if is_cleared and commit:
            CustomUser.objects.filter(pk=user.pk).update(profile_photo=None)

        if commit:
            new_photo_name = user.profile_photo.name if (user.profile_photo and hasattr(user.profile_photo, 'name')) else ''
            # If photo changed or was removed, permanently delete the old photo from disk
            if old_photo_name and old_photo_name != new_photo_name and 'default' not in str(old_photo_name).lower():
                try:
                    from django.core.files.storage import default_storage
                    if default_storage.exists(old_photo_name):
                        default_storage.delete(old_photo_name)
                except Exception:
                    pass

            profile, _ = Profile.objects.get_or_create(user=user)
            if user.city:
                profile.city_hometown = user.city
            profile.profile_photo = None if is_cleared else user.profile_photo
            profile.father_name = user.father_name or ''
            profile.mother_name = user.mother_name or ''
            profile.address = user.address or ''
            profile.bio = user.bio or ''
            profile.save()
            if is_cleared:
                Profile.objects.filter(pk=profile.pk).update(profile_photo=None)
            user.profile = profile
        return user


# =========================
# PROFILE FORM
# =========================

class ProfileForm(forms.ModelForm):

    class Meta:
        model = Profile
        fields = [
            'father_name',
            'mother_name',
            'city_hometown',
            'bio',
            'education',
            'profile_photo',
            'address',
        ]
        widgets = {
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control'}),
            'education': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control'}),
            'profile_photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'city_hometown': forms.Select(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_profile_photo(self):
        photo = self.cleaned_data.get('profile_photo')
        if photo and hasattr(photo, 'file') and 'profile_photo' in self.files:
            photo = validate_image_file(photo, max_size_mb=5)
        return photo


# =========================
# PASSWORD RESET FORMS
# =========================

from django.contrib.auth.password_validation import validate_password


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label="Registered Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control rounded-pill py-2 px-3',
            'placeholder': 'Enter your registered email address',
            'autofocus': True,
            'autocomplete': 'email'
        })
    )


class PasswordResetVerifyForm(forms.Form):
    code = forms.CharField(
        required=True,
        max_length=6,
        min_length=6,
        label="6-Digit Verification Code",
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center fw-bold fs-3 rounded-4',
            'placeholder': '••••••',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
            'autofocus': True,
            'style': 'letter-spacing: 0.35rem;'
        })
    )

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip()
        if not code.isdigit():
            raise forms.ValidationError("Verification code must contain 6 numbers.")
        return code


class PasswordResetSetNewForm(forms.Form):
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control rounded-pill py-2 px-3',
            'placeholder': 'Enter your new password',
            'autocomplete': 'new-password',
            'autofocus': True
        })
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control rounded-pill py-2 px-3',
            'placeholder': 'Re-type your new password',
            'autocomplete': 'new-password'
        })
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("new_password1")
        p2 = cleaned_data.get("new_password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error('new_password2', "Passwords do not match. Please verify and re-type.")
            elif self.user:
                validate_password(p1, user=self.user)
        return cleaned_data


class RateLimitedAuthenticationForm(AuthenticationForm):
    """
    Protects user accounts against credential brute-force attacks.
    Enforces a temporary 15-minute lock after 5 consecutive failed attempts
    for the specific (username, IP) pair. This prevents an external attacker
    from locking out legitimate account owners from their own devices/IPs.
    Also enforces an IP-level threshold to block high-frequency password spraying.
    """
    def clean(self):
        username = (self.cleaned_data.get('username') or '').strip().lower()
        client_ip = get_client_ip(self.request) if self.request else 'unknown'

        if client_ip:
            ip_lock_key = f"login_ip_lock_{client_ip}"
            if cache.get(ip_lock_key):
                raise forms.ValidationError(
                    "Too many failed login attempts from this network. Please try again in 15 minutes."
                )

        if username and client_ip:
            pair_lock_key = f"login_lock_{username}_{client_ip}"
            if cache.get(pair_lock_key):
                raise forms.ValidationError(
                    "This account is temporarily locked due to multiple failed login attempts. Please try again in 15 minutes."
                )

        try:
            return super().clean()
        except forms.ValidationError as e:
            if client_ip:
                ip_attempt_key = f"login_ip_attempts_{client_ip}"
                ip_attempts = cache.get(ip_attempt_key, 0) + 1
                if ip_attempts >= 20:
                    cache.set(f"login_ip_lock_{client_ip}", True, timeout=900)
                    cache.delete(ip_attempt_key)
                    raise forms.ValidationError(
                        "Too many failed login attempts from this network. Access temporarily suspended for 15 minutes."
                    )
                else:
                    cache.set(ip_attempt_key, ip_attempts, timeout=900)

            if username and client_ip:
                pair_attempt_key = f"login_attempts_{username}_{client_ip}"
                attempts = cache.get(pair_attempt_key, 0) + 1
                if attempts >= 5:
                    cache.set(f"login_lock_{username}_{client_ip}", True, timeout=900)  # 15 min lock
                    cache.delete(pair_attempt_key)
                    raise forms.ValidationError(
                        "Too many failed login attempts. This account is temporarily locked for 15 minutes."
                    )
                else:
                    cache.set(pair_attempt_key, attempts, timeout=900)
            raise e

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        username = user.get_username().strip().lower()
        client_ip = get_client_ip(self.request) if self.request else 'unknown'
        if client_ip:
            cache.delete(f"login_attempts_{username}_{client_ip}")
            cache.delete(f"login_lock_{username}_{client_ip}")