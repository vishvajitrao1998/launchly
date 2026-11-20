"""Page views only render templates; data arrives through /api/ via JS."""
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render,get_object_or_404
from . import emails
from .catalog import PLATFORMS, PLATFORM_MAP, SOCIAL
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .ratelimit import by_field, ratelimit
from . import emails, services
from .models import Profile

from django.http import Http404
from django.utils.safestring import mark_safe

from . import seo
from .api import plain_text, render_description
from .models import Category, Product
from .services import display_name

BACKEND = "django.contrib.auth.backends.ModelBackend"


from .forms import SignupForm

def top_page(request):
    return render(request, "top.html")

def home(request):
    q = request.GET.get("q")
    s = seo.build(request, noindex=bool(q), canonical="/", jsonld=[seo.organization(), seo.website()])
    return render(request, "home.html", {"seo": s})

def category_page(request, slug=""):
    if not slug:
        return render(request, "category.html", {"slug": ""})
    cat = get_object_or_404(Category, slug=slug)
    path = f"/category/{cat.slug}/"
    s = seo.build(
        request, title=f"Best {cat.name} products · {seo.SITE}", canonical=path,
        description=f"Discover the best {cat.name} products on {seo.SITE}. Browse top-ranked and newest launches and upvote your favourites.",
        jsonld=[seo.breadcrumbs([("Home", "/"), ("Products", "/products/"), (cat.name, path)])])
    return render(request, "category.html", {"slug": cat.slug, "seo": s})


def pricing(request):
    return render(request, "pricing.html")


def advertise(request):
    return render(request, "advertise.html")


def product_page(request, slug):
    p = (Product.objects.select_related("category", "owner").prefetch_related("screenshots", "tags")
         .filter(slug=slug).first())
    u = request.user
    if not p or not (p.is_live or (u.is_authenticated and (u == p.owner or u.is_staff))):
        raise Http404                                           # real 404 status, not an empty page
    desc_html = render_description(p.description)
    shots = list(p.screenshots.all())
    image = shots[0].image.url if shots else (p.logo.url if p.logo else None)
    path = f"/product/{p.slug}/"
    s = seo.build(
        request, title=f"{seo.clip(f'{p.name}: {p.tagline}', 58)} · {seo.SITE}",
        description=seo.clip(plain_text(p.description) or p.tagline), image=image, canonical=path,
        og_type="article", card="summary_large_image" if shots else "summary", noindex=not p.is_live,
        jsonld=[
            {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": p.name,
             "description": seo.clip(plain_text(p.description) or p.tagline, 300), "url": seo.abs_url(path),
             "image": seo.abs_url(image) if image else None, "applicationCategory": "WebApplication",
             "genre": p.category.name, "sameAs": p.website_url,
             "datePublished": p.launch_at.isoformat() if p.launch_at else None,
             "author": {"@type": "Person", "name": display_name(p.owner)},             
             "operatingSystem": ", ".join(PLATFORM_MAP[k][0] for k in (p.platforms or []) if k in PLATFORM_MAP) or None,
             "keywords": ", ".join(t.name for t in p.tags.all() if t.is_active) or None,},
            seo.breadcrumbs([("Home", "/"), (p.category.name, f"/category/{p.category.slug}/"), (p.name, path)]),
        ])
    return render(request, "product.html", {"seo": s, "product": p, "description_html": mark_safe(desc_html)})


@login_required
def submit(request):
    return render(request, "submit.html", {
        "edit_id": request.GET.get("edit", ""), "platforms": PLATFORMS,
        "pricing": Product._meta.get_field('pricing_model').choices, "social": [(k, label) for k, label, _ in SOCIAL]})


@login_required
def dashboard(request):
    return render(request, "dashboard.html")


@staff_member_required
def review(request):
    return render(request, "review.html")

@ratelimit("signup", 10, 3600)
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

@ratelimit("verify-resend-ip", 10, 3600)
@ratelimit("verify-resend-email", 3, 3600,
           key=lambda r: (r.POST.get("email") or r.session.get("verify_email") or "").strip().lower())
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

@ratelimit("verify-link", 30, 3600, methods=("GET",))
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
