"""JSON API. Pages are plain templates; the browser fills them from these endpoints."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from PIL import Image
from . import services
from .models import AdSlot, Category, Like, Plan, Product, Upvote, ProductScreenshot, Profile, Payment, ProductStat, Tag
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.conf import settings
import html as _html
import re
import nh3
from django.template.defaultfilters import linebreaks
from rest_framework.decorators import throttle_classes
from rest_framework.throttling import AnonRateThrottle

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.dateparse import parse_date

from .catalog import MAX_TAGS, PLATFORM_MAP, clean_social, normalize_tag, tag_slug

from .throttles import AccountThrottle, BASE, PasswordThrottle, SubmitThrottle, VoteThrottle

def paginate(request, qs, fn, size=12):
    try:
        size = min(max(int(request.GET.get("page_size", size)), 1), 50)
    except ValueError:
        pass
    pg = Paginator(qs, size)
    try:
        page = pg.page(request.GET.get("page") or 1)
    except (EmptyPage, PageNotAnInteger):
        page = pg.page(1)
    return {"results": [fn(o) for o in page.object_list], "page": page.number,
            "pages": pg.num_pages, "total": pg.count, "start": page.start_index()}

# ---------------------------------------------------------------- helpers ---
def user_state(request):
    if not request.user.is_authenticated:
        return set(), set()
    u = request.user
    return (set(Upvote.objects.filter(user=u).values_list("product_id", flat=True)),
            set(Like.objects.filter(user=u).values_list("product_id", flat=True)))


def cat_dict(c):
    return {"name": c.name, "slug": c.slug, "icon": c.icon, "color": c.color}


def product_dict(p, state=(set(), set()), sponsored=False):
    up, lk = state
    return {
        "id": p.id, "slug": p.slug, "name": p.name, "tagline": p.tagline,
        "logo": p.logo.url if p.logo else "", "website_url": p.website_url,
        "category": cat_dict(p.category), "is_premium": p.is_premium,
        "upvotes": p.upvote_count, "likes": p.like_count,
        "upvoted": p.id in up, "liked": p.id in lk,
        "launch_at": p.launch_at, "sponsored": sponsored,
    }


# ------------------------------------------------------------ public reads ---
@api_view(["GET"])
def me(request):
    u = request.user
    if not u.is_authenticated:
        return Response({"authenticated": False})
    return Response({"authenticated": True, "username": u.username, "is_staff": u.is_staff,
                     "credits": services.credits_for(u), "can_social": services.has_social_links(u),})


@api_view(["GET"])
def categories(request):
    now = timezone.now()
    qs = Category.objects.annotate(
        n=Count("products", filter=Q(products__status="approved", products__launch_at__lte=now)))
    return Response([{**cat_dict(c), "count": c.n} for c in qs])


@api_view(["GET"])
def products(request):
    qs = Product.objects.live().select_related("category")
    if c := request.GET.get("category"):
        qs = qs.filter(category__slug=c)
    if t := request.GET.get("tag"):
        qs = qs.filter(tags__slug=t, tags__is_active=True)
    if q := request.GET.get("q", "").strip():
        qs = qs.filter(Q(name__icontains=q) | Q(tagline__icontains=q) | Q(tags__name__icontains=q)).distinct()
    qs = qs.order_by("-launch_at" if request.GET.get("sort") == "new" else "-upvote_count", "-launch_at")
    state = user_state(request)
    return Response(paginate(request, qs, lambda p: product_dict(p, state), size=settings.PAGE_SIZES["products"]))


def _maker_about(owner):
    prof = getattr(owner, "profile", None)
    about, links = (prof.about, prof.social_links or {}) if prof else ("", {})
    if not about and not links:
        return None
    return {"name": services.display_name(owner), "about": about, "links": links}

@api_view(["GET"])
def product_detail(request, slug):
    p = get_object_or_404(Product.objects.select_related("category", "owner__profile").prefetch_related("screenshots", "tags"), slug=slug)
    if not p.is_live and not (request.user.is_authenticated and (request.user == p.owner or request.user.is_staff)):
        return Response({"detail": "Not found."}, status=404)
    d = product_dict(p, user_state(request))
    audience=p.audience
    problem=p.problem 
    solution=p.solution
    unique_value=p.unique_value
    platforms=[{"key": k, "label": PLATFORM_MAP[k][0], "icon": PLATFORM_MAP[k][1]} for k in (p.platforms or []) if k in PLATFORM_MAP],
    pricing=({"key": p.pricing_model, "label": p.get_pricing_model_display()} if p.pricing_model else None),
    tags=[{"name": t.name, "slug": t.slug} for t in p.tags.all() if t.is_active],
    social_links=(p.social_links if p.social_links and services.has_social_links(p.owner) else {}),
    d.update(
        description=render_description(p.description), 
        maker=services.display_name(p.owner), 
        is_live=p.is_live, 
        status=p.status, 
        screenshots=[s.image.url for s in p.screenshots.all()],
        audience=audience, 
        platforms=platforms, 
        pricing=pricing,
        tags=tags,
        social_links=social_links,
        problem=problem,
        solution=solution,
        unique_value=unique_value,
        maker_about=_maker_about(p.owner),
        )
    return Response(d)
 

@api_view(["GET"])
def feed(request):
    """Everything the home page needs in ONE request."""
    state = user_state(request)
    today = timezone.localdate()
    cur = services.get_currency(request)
    ads = {}
    for a in AdSlot.objects.active_on(today).select_related("product__category"):
        if a.product.status == Product.Status.APPROVED:
            ads[(a.slot_type, a.category_id, a.position)] = a.product

    def ad_or_open(slot_type, cat=None, pos=1):
        p = ads.get((slot_type, cat.id if cat else None, pos))
        if p:
            return product_dict(p, state, sponsored=True)
        return {"slot_open": True, "slot_type": slot_type, "category": cat.slug if cat else "", "position": pos,
                "label": services.slot_label(slot_type, cat, pos), "price": services.slot_price(slot_type, cur)}

    sections = []
    live = Product.objects.live().select_related("category")
    for c in Category.objects.all():
        sponsored_ids = {p.id for k, p in ads.items() if k[1] == c.id}
        organic = list(live.filter(category=c).exclude(id__in=sponsored_ids).order_by("-upvote_count", "-launch_at")[:10])
        has_ad = any((t, c.id, 1) in ads for t in ("cat_first", "cat_third"))
        if not organic and not has_ad:
            continue
        # Positions 1 and 3 are paid slots; a booked one always shows, however many apps the category has.
        items = [ad_or_open("cat_first", c)]
        if organic:
            items.append(product_dict(organic.pop(0), state))
        items.append(ad_or_open("cat_third", c))
        items += [product_dict(p, state) for p in organic]
        sections.append({"category": cat_dict(c), "items": items})
        limit = settings.PAGE_SIZES['TopProductLimit']

        def top_block(title, kind, offset, limit=limit):
            s, e, _, _ = services.period_range(kind, offset)
            qs = live.filter(launch_at__gte=s, launch_at__lt=e).order_by("-upvote_count", "-launch_at")[:limit]
            return {"title": title, "kind": kind, "offset": offset,
                    "items": [product_dict(p, state) for p in qs]}

    return Response({
        "hero": ad_or_open("hero"),
        "spotlight": [ad_or_open("spotlight", None, i) for i in (1, 2, 3)],
        "sections": sections,
        "latest": [product_dict(p, state) for p in live.order_by("-launch_at")[:6]],
        "top": [
            top_block("Top Products Launching Today", "day", 0),
            top_block("Yesterday's Top Products", "day", 1),
            top_block("Last Week's Top Products", "week", 1),
            top_block("Last Month's Top Products", "month", 1),
        ],
    })


@api_view(["GET"])
def ad_board(request):
    """Which advertisement slot is booked, for the next 4 weeks."""
    today = timezone.localdate()
    weeks = [{"from": today + timedelta(days=7 * i), "to": today + timedelta(days=7 * i + 6)} for i in range(4)]
    held = list(AdSlot.objects.held().filter(ends_on__gte=today).select_related("product"))
    rows = []
    cur = services.get_currency(request)
    for d in services.slot_defs():
        cat = d["category"]
        ident = (d["slot_type"], cat.id if cat else None, d["position"])
        mine = [b for b in held if (b.slot_type, b.category_id, b.position) == ident]
        cells = []
        for w in weeks:
            b = next((b for b in mine if b.starts_on <= w["to"] and b.ends_on >= w["from"]), None)
            cells.append(None if not b else {
                "name": b.product.name, "slug": b.product.slug,
                "logo": b.product.logo.url if b.product.logo else "",
                "pending": b.status != AdSlot.Status.ACTIVE, "until": b.ends_on})
        rows.append({
            "key": f"{d['slot_type']}:{cat.slug if cat else '-'}:{d['position']}",
            "slot_type": d["slot_type"], "position": d["position"],
            "category": cat.slug if cat else "", "icon": cat.icon if cat else "📣",
            "group": cat.name if cat else "Home page",
            "label": services.slot_label(d["slot_type"], cat, d["position"]),
            "price": services.slot_price(d["slot_type"], cur), "cells": cells})
    return Response({"weeks": weeks, "rows": rows})


@api_view(["GET"])
def pricing(request):
    cur = services.get_currency(request)
    plans = [{"slug": p.slug, "name": p.name, "tagline": p.tagline, "price": services.plan_price(p, cur),
              "period_days": p.period_days, "premium_launches": p.premium_launches,
              "features": p.features, "highlighted": p.highlighted} for p in Plan.objects.all()]
    ads = [{"slot_type": k, "name": services.SLOT_INFO[k][0], "description": services.SLOT_INFO[k][1],
            "price": v[cur]} for k, v in settings.AD_PRICING.items()]
    return Response({"currency": cur, "plans": plans, "ads": ads})
 

# ----------------------------------------------------------- like / upvote ---
def _toggle(model, field, pk, user):
    product = get_object_or_404(Product.objects.live(), pk=pk)
    with transaction.atomic():
        obj, created = model.objects.get_or_create(user=user, product=product)
        if not created:
            obj.delete()
        Product.objects.filter(pk=pk).update(**{field: F(field) + (1 if created else -1)})
    product.refresh_from_db(fields=[field])
    return Response({"active": created, "count": getattr(product, field)})


@api_view(["POST"])
@throttle_classes(BASE + [VoteThrottle])
@permission_classes([IsAuthenticated])
def toggle_upvote(request, pk):
    return _toggle(Upvote, "upvote_count", pk, request.user)


@api_view(["POST"])
@throttle_classes(BASE + [VoteThrottle])
@permission_classes([IsAuthenticated])
def toggle_like(request, pk):
    return _toggle(Like, "like_count", pk, request.user)


# -------------------------------------------------------- maker: submission ---
DESC_MIN, DESC_MAX = 20, 2000
ALLOWED_TAGS = {"p", "br", "strong", "em", "u", "s", "ul", "ol", "li", "a"}


def clean_html(h):
    return nh3.clean(h or "", tags=ALLOWED_TAGS, attributes={"a": {"href"}},
                     url_schemes={"http", "https", "mailto"})


def plain_text(h):
    """Visible text only (used for the character limit and for previews)."""
    h = re.sub(r"</(p|li)>|<br\s*/?>", " ", h or "")
    return _html.unescape(nh3.clean(h, tags=set())).replace("\xa0", " ").strip()


def render_description(d):
    """Safe HTML for display. Old plain-text descriptions are converted to paragraphs."""
    if not re.search(r"<[a-zA-Z][^>]*>", d or ""):
        return str(linebreaks(d or "", autoescape=True))
    return clean_html(d)


QA_FIELDS = ("audience", "problem", "solution", "unique_value")
PLATFORM_KEYS = set(PLATFORM_MAP)


def save_tags(product, names):
    tags = []
    for n in names:
        tag, _ = Tag.objects.get_or_create(slug=tag_slug(n), defaults={"name": n})
        tags.append(tag)
    product.tags.set(tags)

class ProductForm(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field="slug", queryset=Category.objects.all())
    launch_mode = serializers.ChoiceField(choices=["now", "schedule"], write_only=True, default="now")
    premium = serializers.BooleanField(write_only=True, default=False)
    platforms = serializers.JSONField(required=False)
    social_links = serializers.JSONField(required=False)
    tags = serializers.JSONField(required=False, write_only=True)

    class Meta:
        model = Product
        fields = ["name", "tagline", "description", "website_url", "logo", "category", "scheduled_for",
                  "launch_mode", "premium", "pricing_model", "platforms", "social_links", "tags", *QA_FIELDS]
        extra_kwargs = {k: {"required": True, "allow_blank": False, "min_length": 10, "max_length": 600} for k in QA_FIELDS}
        extra_kwargs["pricing_model"] = {"required": True, "allow_blank": False}

    def validate_logo(self, f):
        if f and f.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Logo must be under 2 MB.")
        return f

    def validate_description(self, v):
        clean = clean_html(v)
        n = len(plain_text(clean))
        if n < DESC_MIN:
            raise serializers.ValidationError(f"Description must be at least {DESC_MIN} characters.")
        if n > DESC_MAX + 10:
            raise serializers.ValidationError(f"Description is too long ({n}/{DESC_MAX} characters).")
        return clean

    def validate_platforms(self, v):
        if not isinstance(v, list) or not v or any(x not in PLATFORM_KEYS for x in v):
            raise serializers.ValidationError("Choose at least one platform.")
        return list(dict.fromkeys(v))

    def validate_social_links(self, v):
        try:
            return clean_social(v if isinstance(v, dict) else {})
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_tags(self, v):
        if not isinstance(v, list):
            raise serializers.ValidationError("Invalid tags.")
        if len(v) > MAX_TAGS:
            raise serializers.ValidationError(f"You can add up to {MAX_TAGS} tags.")
        names, seen = [], set()
        for raw in v:
            try:
                n = normalize_tag(raw)
            except ValueError as e:
                raise serializers.ValidationError(str(e))
            if tag_slug(n) not in seen:
                seen.add(tag_slug(n))
                names.append(n)
        if Tag.objects.filter(slug__in=seen, is_active=False).exists():
            raise serializers.ValidationError("One of those tags isn't allowed.")
        return names

    def validate(self, a):
        if a.pop("launch_mode", "now") == "schedule":
            s = a.get("scheduled_for")
            if not s or s < timezone.now() + timedelta(hours=1):
                raise serializers.ValidationError({"scheduled_for": "Pick a time at least 1 hour from now."})
        else:
            a["scheduled_for"] = None
        if "social_links" in a and not services.has_social_links(self.context["request"].user):
            a.pop("social_links")            # Scale-plan feature: ignored for everyone else
        return a

    def create(self, vd):
        vd.pop("premium", None)
        tags = vd.pop("tags", None)
        p = super().create(vd)
        save_tags(p, tags or [])
        return p

    def update(self, inst, vd):
        vd.pop("premium", None)
        tags = vd.pop("tags", None)
        p = super().update(inst, vd)
        if tags is not None:
            save_tags(p, tags)
        return p


def owner_dict(p, state):
    d = product_dict(p, state)
    audience=p.audience, 
    problem=p.problem, 
    solution=p.solution, 
    unique_value=p.unique_value,
    pricing_model=p.pricing_model, 
    platforms=p.platforms or [], 
    social_links=p.social_links or {},
    tags=[t.name for t in p.tags.all()],
    d.update(
        status=p.status, 
        admin_note=p.admin_note, 
        scheduled_for=p.scheduled_for,
        is_live=p.is_live, 
        description=p.description, 
        screenshots=[{"id": s.id, "url": s.image.url} for s in p.screenshots.all()],
        description_text=plain_text(p.description), 
        audience=audience,
        pricing_model=pricing_model,
        tags=tags,
        problem=problem,
        solution=solution,
        unique_value=unique_value,
        social_links=social_links,
        platforms=platforms
        )
    return d


@api_view(["GET", "POST"])
@throttle_classes(BASE + [SubmitThrottle])
@permission_classes([IsAuthenticated])
def my_products(request):
    if request.method == "GET":
        state = user_state(request)
        qs = (Product.objects.filter(owner=request.user).select_related("category")
              .prefetch_related("screenshots", "tags").order_by("-created_at"))
        if st := request.GET.get("status"):
            qs = qs.filter(status=st)
        return Response(paginate(request, qs, lambda p: owner_dict(p, state), size=settings.PAGE_SIZES["mine"]))

    s = ProductForm(data=request.data, context={"request": request})
    s.is_valid(raise_exception=True)
    files, _ = check_screenshots(request)
    premium = s.validated_data.get("premium", False)
    if premium and not services.consume_credit(request.user):
        return Response({"detail": "You have no premium launch credits left. Pick a plan on the Pricing page first."}, status=402)
    p = s.save(owner=request.user, is_premium=premium, status=Product.Status.PENDING)
    store_screenshots(p, files, [])
    return Response(owner_dict(p, user_state(request)), status=201)


@api_view(["GET", "PATCH"])
@throttle_classes(BASE + [SubmitThrottle])
@permission_classes([IsAuthenticated])
def my_product(request, pk):
    p = get_object_or_404(Product.objects.select_related("category"), pk=pk, owner=request.user)
    if request.method == "GET":
        return Response(owner_dict(p, user_state(request)))
    if p.status not in (Product.Status.PENDING, Product.Status.NEEDS_INFO):
        return Response({"detail": "Only launches that are in review or need info can be edited."}, status=400)
    s = ProductForm(p, data=request.data, partial=True, context={"request": request})
    s.is_valid(raise_exception=True)
    files, remove = check_screenshots(request, p)
    s.save(status=Product.Status.PENDING)
    store_screenshots(p, files, remove)
    return Response(owner_dict(p, user_state(request)))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_ads(request):
    qs = AdSlot.objects.filter(product__owner=request.user).select_related("product", "category").order_by("-created_at")[:50]
    return Response([{
        "id": a.id, "product": a.product.name, "label": services.slot_label(a.slot_type, a.category, a.position),
        "group": a.category.name if a.category else "Home page", "starts_on": a.starts_on,
        "ends_on": a.ends_on, "status": a.status} for a in qs])


# ----------------------------------------------------------- admin: review ---
@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_queue(request):
    status = request.GET.get("status", "pending")
    counts = dict(Product.objects.values_list("status").annotate(n=Count("id")))
    qs = (Product.objects.filter(status=status).select_related("category", "owner")
          .prefetch_related("screenshots", "tags").order_by("created_at"))

    def row(p):
        d = owner_dict(p, (set(), set()))
        d["owner"] = {"username": p.owner.username, "email": p.owner.email}
        return d
    return Response({"counts": counts, **paginate(request, qs, row, size=settings.PAGE_SIZES["queue"])})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_review(request, pk):
    p = get_object_or_404(Product, pk=pk)
    try:
        services.review_product(p, request.data.get("action"), request.data.get("message", ""))
    except ValueError as e:
        return Response({"detail": str(e)}, status=400)
    return Response({"ok": True, "status": p.status})



MAX_SHOTS = 3


def _ids(request, key):
    getter = getattr(request.data, "getlist", None)
    return [int(x) for x in (getter(key) if getter else []) if str(x).isdigit()]


def check_screenshots(request, product=None):
    files, remove = request.FILES.getlist("screenshots"), _ids(request, "remove_screenshots")
    keep = product.screenshots.exclude(id__in=remove).count() if product else 0
    err = lambda m: serializers.ValidationError({"screenshots": [m]})
    if keep + len(files) > MAX_SHOTS:
        raise err(f"You can upload at most {MAX_SHOTS} screenshots.")
    for f in files:
        if f.size > 3 * 1024 * 1024:
            raise err("Each screenshot must be under 3 MB.")
        try:
            Image.open(f).verify(); f.seek(0)
        except Exception:
            raise err(f"{f.name} is not a valid image.")
    return files, remove


def store_screenshots(product, files, remove):
    if remove:
        product.screenshots.filter(id__in=remove).delete()
    start = product.screenshots.count()
    for i, f in enumerate(files):
        ProductScreenshot.objects.create(product=product, image=f, order=start + i)



LIMITS = {"day": 60, "week": 104, "month": 36}


@api_view(["GET"])
def top(request):
    kind = request.GET.get("kind", "day")
    if kind not in LIMITS:
        kind = "day"
    try:
        offset = min(max(int(request.GET.get("offset", 0)), 0), LIMITS[kind])
    except ValueError:
        offset = 0
    s, e, label, sub = services.period_range(kind, offset)
    qs = (Product.objects.live().filter(launch_at__gte=s, launch_at__lt=e)
          .select_related("category").order_by("-upvote_count", "-launch_at"))
    state = user_state(request)
    data = paginate(request, qs, lambda p: product_dict(p, state), size=settings.PAGE_SIZES["top"])
    data.update(kind=kind, offset=offset, label=label, sub=sub,
                has_prev=offset < LIMITS[kind], has_next=offset > 0)
    return Response(data)


@api_view(["GET"])
def rail(request):
    """The two right-sidebar ad slots."""
    cur = services.get_currency(request)
    booked = {a.position: a.product for a in AdSlot.objects.active_on(timezone.localdate())
              .filter(slot_type="sidebar", product__status=Product.Status.APPROVED)
              .select_related("product__category")}
    out = []
    for pos in (1, 2):
        p = booked.get(pos)
        out.append(product_dict(p, sponsored=True) if p else {
            "slot_open": True, "slot_type": "sidebar", "category": "", "position": pos,
            "label": services.slot_label("sidebar", None, pos), "price": services.slot_price("sidebar", cur)})
    return Response({"ads": out})


# ------------------------------------------------------------- account ---
class ProfileForm(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    display_name = serializers.CharField(max_length=40, allow_blank=True, required=False)
    about = serializers.CharField(max_length=600, allow_blank=True, required=False)
    social_links = serializers.JSONField(required=False)


def _profile_data(u, prof):
    return {"username": u.username, "email": u.email, "first_name": u.first_name,
            "last_name": u.last_name, "display_name": prof.display_name,
            "about": prof.about, "social_links": prof.social_links or {},
            "has_password": u.has_usable_password(), "google": bool(prof.google_id)}

def validate_social_links(self, v):
        try:
            return clean_social(v if isinstance(v, dict) else {})
        except ValueError as e:
            raise serializers.ValidationError(str(e))


@api_view(["GET", "PATCH"])
@throttle_classes(BASE + [AccountThrottle])
@permission_classes([IsAuthenticated])
def my_profile(request):
    u = request.user
    prof, _ = Profile.objects.get_or_create(user=u)
    if request.method == "PATCH":
        s = ProfileForm(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        u.first_name = d.get("first_name", u.first_name).strip()
        u.last_name = d.get("last_name", u.last_name).strip()
        u.save(update_fields=["first_name", "last_name"])
        if "display_name" in d:
            prof.display_name = d["display_name"].strip()
        if "about" in d:
            prof.about = d["about"].strip()
        if "social_links" in d:
            prof.social_links = d["social_links"]
        prof.save()
    return Response(_profile_data(u, prof))


@api_view(["POST"])
@throttle_classes(BASE + [PasswordThrottle])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    
    """
    from . import emails
    u, d = request.user, request.data
    if u.has_usable_password() and not u.check_password(d.get("current_password", "")):
        return Response({"current_password": ["Current password is incorrect."]}, status=400)
    new = d.get("new_password", "")
    if new != d.get("confirm_password"):
        return Response({"confirm_password": ["Passwords do not match."]}, status=400)
    try:
        validate_password(new, u)
    except DjangoValidationError as e:
        return Response({"new_password": list(e.messages)}, status=400)
    u.set_password(new)
    u.save()
    update_session_auth_hash(request, u)   # stay logged in
    emails.password_changed(u) # sendig email for password change
    return Response({"ok": True})



# ------------------------------------------------------------- billing ---
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def billing(request):
    u, now = request.user, timezone.now()
    sub = services.current_subscription(u)
    plan = None
    if sub:
        p = sub.plan
        paid = Payment.objects.filter(user=u, kind="plan", status="paid", plan=p).order_by("-paid_at").first()
        plan = {"name": p.name, "tagline": p.tagline, "features": p.features,
                "amount": paid.amount if paid else None, "currency": paid.currency if paid else "INR",
                "started": sub.starts_at, "expires": sub.expires_at, "active": sub.expires_at > now,
                "days_left": max((sub.expires_at - now).days, 0),
                "credits_left": sub.credits_left, "credits_total": p.premium_launches}
    return Response({"plan": plan})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_slots(request):
    today = timezone.localdate()
    qs = (AdSlot.objects.held().filter(product__owner=request.user)
          .select_related("product", "category").prefetch_related("payment_set").order_by("-starts_on", "-id"))

    def row(a):
        paid = next((p for p in a.payment_set.all() if p.status == "paid"), None)
        phase = ("pending" if a.status == AdSlot.Status.PENDING else "ended" if a.ends_on < today
                 else "upcoming" if a.starts_on > today else "running")
        return {"id": a.id, "product": a.product.name, "slug": a.product.slug,
                "group": a.category.name if a.category else "Home page",
                "label": services.slot_label(a.slot_type, a.category, a.position),
                "starts_on": a.starts_on, "ends_on": a.ends_on, "phase": phase,
                "amount": paid.amount if paid else None, "currency": paid.currency if paid else None}
    return Response(paginate(request, qs, row, size=6))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_payments(request):
    qs = (Payment.objects.filter(user=request.user, status__in=["paid", "failed"])
          .select_related("plan", "ad_slot__product").order_by("-created_at"))

    def row(x):
        what = (f"{x.plan.name} plan" if x.plan else
                f"Ad slot: {x.ad_slot.product.name}" if x.ad_slot else x.get_kind_display())
        return {"what": what, "amount": x.amount, "currency": x.currency, "status": x.status,
                "date": x.paid_at or x.created_at, "ref": x.razorpay_payment_id or x.razorpay_order_id}
    return Response(paginate(request, qs, row, size=8))


# ----------------------------------------------------------- analytics ---
class TrackThrottle(AnonRateThrottle):
    rate = "60/min"

    def get_cache_key(self, request, view):   # per IP, for logged-in users too
        return self.cache_format % {"scope": "track", "ident": self.get_ident(request)}


@api_view(["POST"])
@throttle_classes([TrackThrottle])
def track(request, pk):
    kind = request.data.get("kind")
    if kind not in ("view", "click"):
        return Response({"detail": "Unknown event."}, status=400)
    p = get_object_or_404(Product.objects.live(), pk=pk)
    if request.user.is_authenticated and request.user == p.owner:
        return Response({"ok": True})            # your own visits don't count
    stat, _ = ProductStat.objects.get_or_create(product=p, day=timezone.localdate())
    col = f"{kind}s"
    ProductStat.objects.filter(pk=stat.pk).update(**{col: F(col) + 1})
    return Response({"ok": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics(request):
    if not services.has_analytics(request.user):
        return Response({"locked": True})

    start, end = _revenue_range(request)          # custom ?start=&end= or preset ?days=
    days = (end - start).days + 1
    prev_start = start - timedelta(days=days)
    end_excl = services._aware(end + timedelta(days=1))

    mine = Product.objects.filter(owner=request.user)
    options = [{"id": p.id, "name": p.name} for p in mine.order_by("name")]
    pid = request.GET.get("product", "")
    prods = list(mine.filter(pk=pid) if pid.isdigit() else mine)
    ids = [p.id for p in prods]

    labels = [start + timedelta(days=i) for i in range(days)]
    idx = {d: i for i, d in enumerate(labels)}
    keys = ("views", "clicks", "upvotes", "likes")
    series = {k: [0] * days for k in keys}
    per = {i: dict.fromkeys(keys, 0) for i in ids}
    prev = dict.fromkeys(keys, 0)

    for s in ProductStat.objects.filter(product_id__in=ids, day__gte=prev_start, day__lte=end).values("product_id", "day", "views", "clicks"):
        for k in ("views", "clicks"):
            if s["day"] >= start:
                series[k][idx[s["day"]]] += s[k]
                per[s["product_id"]][k] += s[k]
            else:
                prev[k] += s[k]

    lo = services._aware(prev_start)
    for model, key in ((Upvote, "upvotes"), (Like, "likes")):
        # bucketed in Python so it also works on MySQL without timezone tables
        for p_id, created in model.objects.filter(product_id__in=ids, created_at__gte=lo, created_at__lt=end_excl).values_list("product_id", "created_at"):
            d = timezone.localtime(created).date()
            if d >= start:
                series[key][idx[d]] += 1
                per[p_id][key] += 1
            else:
                prev[key] += 1

    totals = {k: {"value": sum(v[k] for v in per.values()), "prev": prev[k]} for k in keys}
    top = []
    for p in prods:
        r = per[p.id]
        top.append({"id": p.id, "name": p.name, "slug": p.slug, **r,
                    "ctr": round(r["clicks"] / r["views"] * 100, 1) if r["views"] else 0})
    top.sort(key=lambda x: (-x["views"], -x["upvotes"]))
    return Response({"locked": False, "days": days, "start": start.isoformat(), "end": end.isoformat(),
                     "products": options, "totals": totals,
                     "series": {"labels": [d.isoformat() for d in labels], **series}, "top": top[:10]})

# ------------------------------------------------------- admin revenue ---
CURRENCIES = ("INR", "USD")


def _revenue_range(request):
    """Custom ?start=&end= (max 366 days) or a preset ?days=7|30|90|365. Returns (start, end) dates."""
    today = timezone.localdate()
    try:
        s, e = parse_date(request.GET.get("start") or ""), parse_date(request.GET.get("end") or "")
    except ValueError:
        s = e = None
    if s and e:
        e = min(e, today)
        s = min(max(s, e - timedelta(days=365)), e)
        return s, e
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30
    days = days if days in (7, 30, 90, 365) else 30
    return today - timedelta(days=days - 1), today


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_revenue(request):
    start, end = _revenue_range(request)
    n = (end - start).days + 1
    prev_start = start - timedelta(days=n)
    end_excl = services._aware(end + timedelta(days=1))
    labels = [start + timedelta(days=i) for i in range(n)]
    idx = {d: i for i, d in enumerate(labels)}
    out = {c: {"total": 0, "prev": 0, "plan": 0, "ad": 0, "count": 0, "failed": 0, "alltime": 0,
               "series": {"plan": [0] * n, "ad": [0] * n}, "items": {}} for c in CURRENCIES}

    rows = (Payment.objects.filter(status="paid", currency__in=CURRENCIES,
                                   paid_at__gte=services._aware(prev_start), paid_at__lt=end_excl)
            .values_list("currency", "kind", "amount", "paid_at", "plan__name", "ad_slot__slot_type"))
    for cur, kind, amt, at, plan_name, slot_type in rows:   # bucketed in Python: works on MySQL without timezone tables
        d, o = timezone.localtime(at).date(), out[cur]
        if d < start:
            o["prev"] += amt
            continue
        if d not in idx:
            continue
        o["total"] += amt
        o[kind] += amt
        o["count"] += 1
        o["series"][kind][idx[d]] += amt
        label = (f"{plan_name} plan" if kind == "plan" and plan_name
                 else services.SLOT_INFO.get(slot_type, ("Ad slot",))[0] if kind == "ad" else kind)
        it = o["items"].setdefault((kind, label), {"amount": 0, "count": 0})
        it["amount"] += amt
        it["count"] += 1

    for r in Payment.objects.filter(status="paid", currency__in=CURRENCIES).values("currency").annotate(t=Sum("amount")):
        out[r["currency"]]["alltime"] = r["t"] or 0
    for r in (Payment.objects.filter(status="failed", currency__in=CURRENCIES,
                                     created_at__gte=services._aware(start), created_at__lt=end_excl)
              .values("currency").annotate(n=Count("id"))):
        out[r["currency"]]["failed"] = r["n"]

    for o in out.values():
        o["items"] = sorted(({"kind": k, "label": l, **v} for (k, l), v in o["items"].items()),
                            key=lambda x: -x["amount"])
    return Response({"days": n, "start": start.isoformat(), "end": end.isoformat(),
                     "labels": [d.isoformat() for d in labels], "currencies": out})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_payments(request):
    start, end = _revenue_range(request)
    lo, hi = services._aware(start), services._aware(end + timedelta(days=1))
    qs = (Payment.objects.select_related("user", "plan", "ad_slot__product")
          .filter(Q(paid_at__gte=lo, paid_at__lt=hi) | Q(paid_at__isnull=True, created_at__gte=lo, created_at__lt=hi))
          .order_by("-created_at"))
    st = request.GET.get("status", "paid")
    if st in ("paid", "failed"):
        qs = qs.filter(status=st)
    cur = request.GET.get("currency", "").upper()
    if cur in CURRENCIES:
        qs = qs.filter(currency=cur)

    def row(x):
        if x.plan:
            what = f"{x.plan.name} plan"
        elif x.ad_slot:
            what = f"{services.SLOT_INFO.get(x.ad_slot.slot_type, ('Ad slot',))[0]} · {x.ad_slot.product.name}"
        else:
            what = x.get_kind_display()
        return {"user": x.user.username, "email": x.user.email, "what": what, "amount": x.amount,
                "currency": x.currency, "status": x.status, "date": x.paid_at or x.created_at,
                "ref": x.razorpay_payment_id or x.razorpay_order_id}
    return Response(paginate(request, qs, row, size=10))


@api_view(["GET"])
def tags(request):
    """Popular tags, or matches while the maker is typing."""
    q = request.GET.get("q", "").strip()
    qs = Tag.objects.filter(is_active=True).annotate(
        n=Count("products", filter=Q(products__status="approved", products__launch_at__lte=timezone.now())))
    if q:
        qs = qs.filter(name__icontains=q)
    return Response([{"name": t.name, "slug": t.slug, "count": t.n} for t in qs.order_by("-n", "name")[:15]])