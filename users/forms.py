from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Profile, Caste, City
from datetime import date

# =========================
# REGISTER FORM
# =========================

class UserRegisterForm(UserCreationForm):

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

    caste_community = forms.ModelChoiceField(
        queryset=Caste.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
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

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')

        if not phone.isdigit():
            raise forms.ValidationError("Enter digits only.")

        if len(phone) != 10:
            raise forms.ValidationError("Enter exactly 10 digits.")

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
            'caste_community',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['full_name'].widget.attrs['placeholder'] = "Full Name"
        self.fields['phone_number'].widget.attrs['placeholder'] = "Phone Number"
        self.fields['password1'].label = "Enter Password"
        self.fields['password2'].label = "Retype Password"


# =========================
# USER UPDATE FORM
# =========================

class UserUpdateForm(forms.ModelForm):

    phone_number = forms.CharField(
        max_length=10,
        min_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10 digit mobile number'
        })
    )

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
        fields = [
            'full_name',
            'email',
            'gender',
            'phone_number',
            'date_of_birth',
            'occupation',
            'height_cm',
            'caste_community',
            'gotra',
            'annual_income',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'height_cm': forms.NumberInput(attrs={'class': 'form-control'}),
            'caste_community': forms.Select(attrs={'class': 'form-control'}),
            'gotra': forms.TextInput(attrs={'class': 'form-control'}),
            'annual_income': forms.NumberInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }


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

        if photo and hasattr(photo, 'content_type'):
            if photo.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Image must be under 2MB")

            if not photo.content_type.startswith('image/'):
                raise forms.ValidationError("File must be an image")

        return photo
    
def clean_height_cm(self):
    height = self.cleaned_data.get("height_cm")
    if height and height <= 0:
        raise forms.ValidationError("Height must be positive")
    return height