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

from django.http import Http404,Http404, HttpResponse
from django.utils.safestring import mark_safe

from . import seo
from .api import plain_text, render_description
from .models import Category, Product
from .services import display_name

from xml.sax.saxutils import escape
from django.views.decorators.clickjacking import xframe_options_exempt

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
    return render(request, "settings.html", {"social": [(k, label) for k, label, _ in SOCIAL]})

@login_required
def embed_page(request):
    return render(request, "embed_code.html")


@xframe_options_exempt                       # this page is meant to be shown inside other people's sites
def embed_card(request, slug):
    p = Product.objects.live().select_related("category").filter(slug=slug).first()
    if not p:
        return HttpResponse('<body style="font:14px sans-serif;color:#7b665a;padding:18px">This product is not available.</body>', status=404)
    resp = render(request, "embed/card.html", {
        "product": p, "site": seo.SITE, "theme": "dark" if request.GET.get("theme") == "dark" else "light",
        "url": seo.abs_url(f"/product/{p.slug}/") + "?ref=embed",
        "initials": "".join(w[0] for w in p.name.split()[:2]).upper() or "?"})
    resp["Cache-Control"] = "public, max-age=300"
    return resp


def badge_svg(request, slug):
    p = get_object_or_404(Product.objects.live(), slug=slug)
    bg, fg, sub, line = (("#1e1814", "#f7eee5", "#b5a495", "#3a3028") if request.GET.get("theme") == "dark"
                         else ("#ffffff", "#2b1d16", "#7b665a", "#eaded0"))
    site = escape(seo.SITE[:14])
    font = 'font-family="Segoe UI,Helvetica,Arial,sans-serif"'
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="250" height="54" viewBox="0 0 250 54" role="img" aria-label="Featured on {site}">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d93f6a"/><stop offset=".6" stop-color="#f2662e"/><stop offset="1" stop-color="#f5a524"/></linearGradient></defs>
<rect x=".5" y=".5" width="249" height="53" rx="12" fill="{bg}" stroke="{line}"/>
<rect x="10" y="10" width="34" height="34" rx="10" fill="url(#g)"/>
<path d="M27 18.5 35.5 33.5H18.5Z" fill="#fff"/>
<text x="54" y="23" {font} font-size="9.5" font-weight="700" letter-spacing="1" fill="{sub}">FEATURED ON</text>
<text x="54" y="42" {font} font-size="18" font-weight="800" fill="{fg}">{site}</text>
<text x="238" y="33" text-anchor="end" {font} font-size="12" font-weight="700" fill="{sub}">&#9650; {int(p.upvote_count)}</text>
</svg>'''
    resp = HttpResponse(svg, content_type="image/svg+xml")
    resp["Cache-Control"] = "public, max-age=3600"
    return resp

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
