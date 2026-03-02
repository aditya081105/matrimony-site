from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class UserRegisterForm(UserCreationForm):

    full_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    occupation = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text=""
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text=""
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + (
            'full_name',
            'occupation',
            'caste_community',
        )

from django.forms import ModelForm
from .models import Profile


class ProfileForm(ModelForm):
    class Meta:
        model = Profile
        fields = ['father_name', 'mother_name', 'city_hometown', 'bio']
        widgets = {
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control'}),
            'city_hometown': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control'}),
        }

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [
            'full_name',
            'occupation',
            'height_cm',
            'caste_community',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'height_cm': forms.NumberInput(attrs={'class': 'form-control'}),
            'caste_community': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If you later add is_approved to CustomUser
        if hasattr(self.instance, 'is_approved') and self.instance.is_approved:
            self.fields['caste_community'].disabled = True

class ProfileForm(ModelForm):
    class Meta:
        model = Profile
        fields = [
            'father_name',
            'mother_name',
            'city_hometown',
            'bio',
            'profile_photo',
        ]
        widgets = {
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control'}),
            'city_hometown': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control'}),
        }
    def clean_profile_photo(self):
        photo = self.cleaned_data.get('profile_photo')

        if photo:
            if photo.size > 2 * 1024 * 1024:  # 2MB limit
                raise forms.ValidationError("Image must be under 2MB")

            if not photo.content_type.startswith('image/'):
                raise forms.ValidationError("File must be an image")

        return photo