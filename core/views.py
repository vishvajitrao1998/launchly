"""Page views only render templates; data arrives through /api/ via JS."""
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from . import emails


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
        # user = form.save()
        login(request, form.save())
        # emails.welcome(user)
        return redirect(request.GET.get("next") or "dashboard")
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
