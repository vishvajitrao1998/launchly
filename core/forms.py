from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, UserCreationForm, AuthenticationForm
from django.urls import reverse

from . import emails


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = get_user_model()
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class ResetRequestForm(PasswordResetForm):
    """Same Django logic, but the mail is sent with our HTML template."""


    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if not list(self.get_users(email)):   # active users with a usable password, case-insensitive
            raise forms.ValidationError("No account found with this email address.")
        return email

    def get_users(self, email):
        return get_user_model()._default_manager.filter(email__iexact=email, is_active=True)

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        path = reverse("password_reset_confirm", kwargs={"uidb64": context["uid"], "token": context["token"]})
        emails.password_reset(context["user"], to_email, settings.SITE_URL.rstrip("/") + path)


class ResetSetForm(SetPasswordForm):
    def save(self, commit=True):
        user = super().save(commit)
        if commit:
            emails.password_changed(user)
        return user


class LoginForm(AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get("username")
        if username:
            u = get_user_model().objects.filter(username=username).first()
            if u and not u.has_usable_password():
                raise forms.ValidationError(
                    "This account uses Google sign-in. Click “Continue with Google”, "
                    "or use “Forgot password?” to set a password.", code="google_only")
        return super().clean()