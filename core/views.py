"""Page views only render templates; data arrives through /api/ via JS."""
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from . import emails

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import emails, services
from .models import Profile

BACKEND = "django.contrib.auth.backends.ModelBackend"


from .forms import SignupForm

def top_page(request):
    return render(request, "top.html")

def home(request):
    return render(request, "home.html")

def category_page(request, slug=""):
    return render(request, "category.html", {"slug": slug})


def pricing(request):
    return render(request, "pricing.html")


def advertise(request):
    return render(request, "advertise.html")


def product_page(request, slug):
    return render(request, "product.html", {"slug": slug})


@login_required
def submit(request):
    return render(request, "submit.html", {"edit_id": request.GET.get("edit", "")})


@login_required
def dashboard(request):
    return render(request, "dashboard.html")


@staff_member_required
def review(request):
    return render(request, "review.html")


def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        Profile.objects.get_or_create(user=user)
        services.send_verification(user)                 # no login yet: they must verify first
        request.session["verify_email"] = user.email
        nxt = request.GET.get("next", "")
        if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
            request.session["post_login_next"] = nxt
        return redirect("verify_sent")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def settings_page(request):
    return render(request, "settings.html")


@login_required
def billing_page(request):
    return render(request, "billing.html")


@login_required
def analytics_page(request):
    return render(request, "analytics.html")


@staff_member_required
def revenue_page(request):
    return render(request, "revenue.html")



def verify_sent(request):
    email = request.session.get("verify_email", "")
    return render(request, "registration/verify_sent.html", {"masked": services.mask_email(email) if email else ""})


@require_POST
def resend_verification(request):
    email = (request.POST.get("email") or request.session.get("verify_email") or "").strip().lower()
    user = get_user_model().objects.filter(email__iexact=email, is_active=True).first() if email else None
    if user and not services.is_verified(user):
        services.send_verification(user)
    request.session["verify_email"] = email
    # same message either way, so nobody can probe which emails have accounts
    messages.info(request, "If that email has an account waiting for verification, a new link is on its way. "
                           "You can request one every minute.")
    return redirect("verify_sent")


def verify_email(request, token):
    user = services.read_verify_token(token)
    if not user:
        return render(request, "registration/verify_failed.html", status=400)
    if not services.mark_verified(user):                 # already verified: don't log anyone in again from an old link
        messages.info(request, "Your email is already verified. Please log in.")
        return redirect("login")
    emails.welcome(user)
    if not user.is_active:
        messages.error(request, "This account has been disabled.")
        return redirect("login")
    login(request, user, backend=BACKEND)
    nxt = request.session.pop("post_login_next", "")
    return redirect(nxt or "dashboard")
