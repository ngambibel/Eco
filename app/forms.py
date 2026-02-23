from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser as User
from django.core.exceptions import ValidationError
import re
from .models import  Abonnement, DemandeReabonnement

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control glass-input',
            'placeholder': 'votre@email.com'
        })
    )
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control glass-input',
            'placeholder': 'Nom d\'utilisateur'
        })
    )
    
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control glass-input password-field',
            'placeholder': 'Mot de passe',
            'id': 'password1'
        })
    )
    
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control glass-input password-field',
            'placeholder': 'Confirmation du mot de passe',
            'id': 'password2'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Un compte avec cet email existe déjà.")
        return email
    
    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if len(password1) < 8:
            raise ValidationError("Le mot de passe doit contenir au moins 8 caractères.")
        if not re.search(r'[A-Z]', password1) or not re.search(r'[a-z]', password1) or not re.search(r'[0-9]', password1):
            raise ValidationError("Le mot de passe doit contenir des majuscules, minuscules et chiffres.")
        return password1

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control glass-input',
            'placeholder': 'Nom d\'utilisateur ou email'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control glass-input password-field',
            'placeholder': 'Mot de passe',
            'id': 'login-password'
        })
    )



