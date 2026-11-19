"""Business rules shared by the API, the Django admin and the webhook."""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from datetime import date, datetime, time, timedelta
from .models import AdSlot, Category, Payment, Product, Subscription, Profile

from django.core import signing
from django.core.cache import cache
from django.urls import reverse

import logging
log = logging.getLogger("core")


SLOT_INFO = {
    "hero": ("Hero Banner", "The big banner at the very top of Home. One advertiser at a time."),
    "spotlight": ("Sponsored Spotlight", "Three featured tiles right under the hero, shown to every visitor."),
    "sidebar": ("Right Sidebar", "Two sponsored tiles in the right rail on Home and the Leaderboard."),
    "cat_first": ("Category · 1st Position", "Pinned to the first spot of a category list, no matter how many apps it has."),
    "cat_third": ("Category · 3rd Position", "Pinned to the third spot of a category list, no matter how many apps it has."),
}
ORDINAL = {1: "1st", 3: "3rd"}


CURRENCIES = ("INR", "USD")


def get_currency(request):
    c = request.COOKIES.get("currency", "INR").upper()
    return c if c in CURRENCIES else "INR"


def slot_price(slot_type, currency="INR"):
    return settings.AD_PRICING[slot_type][currency]


def plan_price(plan, currency="INR"):
    return plan.price_usd if currency == "USD" else plan.price_inr


def slot_label(slot_type, category=None, position=1):
    if slot_type == "hero":
        return "Hero banner"
    if slot_type == "spotlight":
        return f"Spotlight #{position}"
    if slot_type == "sidebar":
        return f"Sidebar #{position}"
    return f"{ORDINAL[1 if slot_type == 'cat_first' else 3]} position"


def slot_defs():
    defs = [{"slot_type": "hero", "category": None, "position": 1}]
    defs += [{"slot_type": "spotlight", "category": None, "position": i} for i in (1, 2, 3)]
    defs += [{"slot_type": "sidebar", "category": None, "position": i} for i in (1, 2)]
    for c in Category.objects.all():
        defs.append({"slot_type": "cat_first", "category": c, "position": 1})
        defs.append({"slot_type": "cat_third", "category": c, "position": 1})
    return defs


def slot_taken(slot_type, category_id, position, start, end):
    return AdSlot.objects.held().filter(
        slot_type=slot_type, category_id=category_id, position=position,
        starts_on__lte=end, ends_on__gte=start,
    ).exists()


# ---- credits ---------------------------------------------------------------
def _live_subs(user):
    return Subscription.objects.filter(user=user, expires_at__gt=timezone.now())


def credits_for(user):
    return _live_subs(user).aggregate(s=Sum("credits_left"))["s"] or 0


def consume_credit(user):
    with transaction.atomic():
        sub = _live_subs(user).select_for_update().filter(credits_left__gt=0).order_by("expires_at").first()
        if not sub:
            return False
        sub.credits_left -= 1
        sub.save(update_fields=["credits_left"])
        return True


def refund_credit(user):
    sub = _live_subs(user).order_by("-expires_at").first()
    if sub:
        Subscription.objects.filter(pk=sub.pk).update(credits_left=F("credits_left") + 1)


# ---- moderation ------------------------------------------------------------
def _mail(product, subject, body):
    if product.owner.email:
        send_mail(subject, body, None, [product.owner.email], fail_silently=True)


def review_product(product, action, message=""):
    """action: approve | reject | request_info | email. Returns the product."""
    message = (message or "").strip()
    dash = f"{settings.SITE_URL}/dashboard/"
    hi = f"Hi {product.owner.first_name or product.owner.username},\n\n"
    sign = "\n\n— The LetsPublic team"

    if action == "approve":
        now = timezone.now()
        product.status = Product.Status.APPROVED
        product.admin_note = ""
        product.launch_at = product.scheduled_for if product.scheduled_for and product.scheduled_for > now else now
        when = "It is live now!" if product.launch_at <= now else f"It will go live on {timezone.localtime(product.launch_at):%d %b %Y, %I:%M %p}."
        _mail(product, f"🎉 {product.name} was approved", f"{hi}Great news — {product.name} has been approved. {when}\n{dash}{sign}")
    elif action == "reject":
        product.status = Product.Status.REJECTED
        product.admin_note = message
        if product.is_premium:
            product.is_premium = False
            refund_credit(product.owner)  # premium credit goes back to the maker
        _mail(product, f"{product.name} was not approved", f"{hi}Unfortunately we could not approve {product.name}.\n\nReason: {message or 'Does not meet our guidelines.'}{sign}")
    elif action == "request_info":
        if not message:
            raise ValueError("Tell the maker what is missing.")
        product.status = Product.Status.NEEDS_INFO
        product.admin_note = message
        _mail(product, f"Action needed: {product.name}", f"{hi}We need a bit more information before we can approve {product.name}:\n\n{message}\n\nUpdate your launch here: {dash}{sign}")
    elif action == "email":
        if not message:
            raise ValueError("Write a message first.")
        _mail(product, f"About {product.name}", f"{hi}{message}{sign}")
        return product
    else:
        raise ValueError("Unknown action.")
    product.save()
    return product


# ---- payments --------------------------------------------------------------
@transaction.atomic
def fulfil_payment(payment, razorpay_payment_id=""):
    """Idempotent: safe to call from both /verify/ and the webhook. Emails go out only once."""
    from . import emails
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == Payment.Status.PAID:
        return payment
    now = timezone.now()
    payment.status = Payment.Status.PAID
    payment.razorpay_payment_id = razorpay_payment_id
    payment.paid_at = now
    payment.save()
    log.info("Payment paid: order=%s user=%s amount=%s %s", payment.razorpay_order_id, payment.user_id, payment.amount, payment.currency)
    if payment.kind == Payment.Kind.PLAN and payment.plan:
        sub = Subscription.objects.create(
            user=payment.user, plan=payment.plan, starts_at=now,
            expires_at=now + timedelta(days=payment.plan.period_days),
            credits_left=payment.plan.premium_launches)
        transaction.on_commit(lambda: emails.plan_activated(payment, sub))
    elif payment.kind == Payment.Kind.AD and payment.ad_slot:
        payment.ad_slot.status = AdSlot.Status.ACTIVE
        payment.ad_slot.save(update_fields=["status"])
        transaction.on_commit(lambda: emails.slot_booked(payment))
    return payment

def fail_payment(payment, reason=""):
    """CREATED -> FAILED (only once): frees the held ad slot and emails the user."""
    from . import emails
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status != Payment.Status.CREATED:
            return payment
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        log.warning("Payment failed: order=%s user=%s reason=%s", payment.razorpay_order_id, payment.user_id, reason)
        if payment.ad_slot_id:
            AdSlot.objects.filter(pk=payment.ad_slot_id, status=AdSlot.Status.PENDING).update(status=AdSlot.Status.CANCELLED)
    emails.payment_failed(payment, reason)
    return payment

def _aware(d):
    return timezone.make_aware(datetime.combine(d, time.min))


def period_range(kind, offset=0):
    """kind: day | week | month. offset 0 = current, 1 = previous... Returns (start, end_exclusive, label, sub)."""
    today = timezone.localdate()
    if kind == "day":
        s = today - timedelta(days=offset)
        e = s + timedelta(days=1)
        label = "Today" if offset == 0 else "Yesterday" if offset == 1 else f"{s:%A}"
        sub = f"{s:%d %b %Y}"
    elif kind == "week":
        s = today - timedelta(days=today.weekday()) - timedelta(weeks=offset)
        e = s + timedelta(days=7)
        label = "This week" if offset == 0 else "Last week" if offset == 1 else f"{offset} weeks ago"
        sub = f"{s:%d %b} – {(e - timedelta(days=1)):%d %b %Y}"
    else:
        y, m = today.year, today.month - offset
        while m <= 0:
            m += 12
            y -= 1
        s = date(y, m, 1)
        e = date(y + (m == 12), m % 12 + 1, 1)
        label = "This month" if offset == 0 else "Last month" if offset == 1 else f"{s:%B}"
        sub = f"{s:%B %Y}"
    return _aware(s), _aware(e), label, sub



def display_name(user):
    """Public name: display name if set, else username."""
    profile = getattr(user, "profile", None)
    return (profile.display_name if profile and profile.display_name else user.username)


def mask_email(email):
    """hello.world@gmail.com -> hello***@gmail.com"""
    if not email or "@" not in email:
        return ""
    local, domain = email.rsplit("@", 1)
    keep = min(5, max(1, len(local) - 3))
    return f"{local[:keep]}***@{domain}"



def current_subscription(user):
    """Latest plan purchase (active or expired), or None = free Starter."""
    return Subscription.objects.filter(user=user).select_related("plan").order_by("-expires_at").first()


def has_analytics(user):
    """True while the user holds an unexpired plan that includes analytics (Scale)."""
    return _live_subs(user).filter(plan__has_analytics=True).exists()


# ------------------------------------------------------ email verification ---
SALT = "email-verify"


def is_verified(user):
    if user.is_staff or user.is_superuser:
        return True
    p = getattr(user, "profile", None)
    return bool(p and (p.email_verified or p.google_id))


def mark_verified(user):
    """True only the first time (so the welcome email is sent once)."""
    prof, _ = Profile.objects.get_or_create(user=user)
    if prof.email_verified:
        return False
    prof.email_verified = True
    prof.save(update_fields=["email_verified"])
    return True


def send_verification(user):
    """False if a link was already sent in the last minute (stops spamming an inbox)."""
    from . import emails
    if not cache.add(f"verify-sent:{user.pk}", 1, 60):
        return False
    token = signing.dumps({"uid": user.pk, "email": user.email.lower()}, salt=SALT)
    link = settings.SITE_URL.rstrip("/") + reverse("verify_email", args=[token])
    emails.verify_email(user, link)
    return True


def read_verify_token(token):
    from django.contrib.auth import get_user_model
    try:
        data = signing.loads(token, salt=SALT, max_age=settings.EMAIL_VERIFY_HOURS * 3600)
    except signing.BadSignature:      # also covers expired links
        return None
    user = get_user_model().objects.filter(pk=data.get("uid")).first()
    return user if user and user.email.lower() == data.get("email") else None   # link dies if the email changed