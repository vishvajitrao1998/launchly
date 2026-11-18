"""Sign in with Google (OpenID Connect, authorization-code flow)."""
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify

from . import emails
from .models import Profile

User = get_user_model()
BACKEND = "django.contrib.auth.backends.ModelBackend"

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def _unique_username(base):
    base = (slugify(base) or "user")[:30]
    name, n = base, 1
    while User.objects.filter(username=name).exists():
        n += 1
        name = f"{base}{n}"
    return name


def google_login(request):
    if not settings.GOOGLE_CLIENT_ID:
        messages.error(request, "Google sign-in is not configured yet.")
        return redirect("login")
    nxt = request.GET.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        request.session["post_login_next"] = nxt
    redirect_uri = settings.SITE_URL.rstrip("/") + reverse("google_callback")
    return oauth.google.authorize_redirect(request, redirect_uri)


def google_callback(request):
    try:
        token = oauth.google.authorize_access_token(request)   # checks state + validates the ID token
    except OAuthError:
        messages.error(request, "Google sign-in was cancelled or failed. Please try again.")
        return redirect("login")

    info = token.get("userinfo") or {}
    sub, email = info.get("sub"), (info.get("email") or "").lower()
    if not sub or not email or not info.get("email_verified"):
        messages.error(request, "Your Google account doesn't have a verified email address.")
        return redirect("login")

    created = False
    profile = Profile.objects.select_related("user").filter(google_id=sub).first()
    if profile:
        user = profile.user
    else:
        user = User.objects.filter(email__iexact=email).first()
        if user:                                             # same verified email -> link
            profile, _ = Profile.objects.get_or_create(user=user)
            if profile.google_id and profile.google_id != sub:
                messages.error(request, "This email is already linked to a different Google account.")
                return redirect("login")
            profile.google_id = sub
            profile.save(update_fields=["google_id"])
        else:                                                # brand-new account, no password
            user = User.objects.create_user(
                username=_unique_username(email.split("@")[0]), email=email,
                first_name=(info.get("given_name") or "")[:150], last_name=(info.get("family_name") or "")[:150])
            Profile.objects.create(user=user, google_id=sub, display_name=(info.get("name") or "")[:40])
            created = True

    if not user.is_active:
        messages.error(request, "This account has been disabled.")
        return redirect("login")

    nxt = request.session.pop("post_login_next", "")
    login(request, user, backend=BACKEND)
    if created:
        emails.welcome(user)
    return redirect(nxt or "dashboard")