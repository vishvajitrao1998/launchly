"""All outgoing emails. Every message uses templates/emails/notify.(html|txt)."""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from . import services

log = logging.getLogger(__name__)


def url(path):
    return settings.SITE_URL.rstrip("/") + path


def money(amount, currency):
    return f"{'₹' if currency == 'INR' else '$'}{amount:,}"


def _day(d):
    return f"{d:%d %b %Y}"


def _deliver(msg):
    try:
        msg.send()
    except Exception:
        log.exception("Email failed: %s", msg.subject)   # never break the request


def send_notification(to, subject, heading, intro, details=None, cta=None, outro="", tone="ok"):
    """cta = (button label, absolute url). details = [(label, value), ...]. tone = ok | bad."""
    if not to:
        return
    ctx = {"subject": subject, "heading": heading, "intro": intro, "details": details or [],
           "cta": cta, "outro": outro, "tone": tone,
           "site_url": settings.SITE_URL, "contact_email": settings.CONTACT_EMAIL}
    msg = EmailMultiAlternatives(subject, render_to_string("emails/notify.txt", ctx), None, [to])
    msg.attach_alternative(render_to_string("emails/notify.html", ctx), "text/html")
    threading.Thread(target=_deliver, args=(msg,), daemon=True).start()   # use Celery later if volume grows


# ---------------------------------------------------------------- emails ---
def welcome(user):
    name = services.display_name(user)
    send_notification(
        user.email, f"Welcome to LetsPublic, {name}", f"Welcome Aboard, {name} 👋",
        "Your LetsPublic account is ready. You can now launch products, upvote your favourites and book ad slots.",
        details=[("Username", user.username)],
        cta=("Launch your first Product", url("/launch-product/")),
        outro="Every launch is reviewed, usually within 48 hours.")


def plan_activated(payment, sub):
    plan = payment.plan
    send_notification(
        payment.user.email, f"Your {plan.name} plan is active", "Payment received. Thank you!",
        f"Your {plan.name} plan is now active.",
        details=[("Plan", plan.name),
                 ("Amount paid", money(payment.amount, payment.currency)),
                 ("Premium launches", f"{sub.credits_left} included"),
                 ("Valid until", _day(timezone.localtime(sub.expires_at))),
                 ("Payment ID", payment.razorpay_payment_id)],
        cta=("Submit a Premium launch", url("/submit/")),
        outro="A Premium credit is used when you tick “Premium launch” on the submit form. Unused credits expire with the plan.")


def slot_booked(payment):
    slot = payment.ad_slot
    where = f"{slot.category.name if slot.category else 'Home page'} · {services.slot_label(slot.slot_type, slot.category, slot.position)}"
    weeks = ((slot.ends_on - slot.starts_on).days + 1) // 7
    send_notification(
        payment.user.email, f"Ad slot booked: {where}", "Your ad slot is confirmed 🎉",
        f"{slot.product.name} will be featured in {where} from {_day(slot.starts_on)} to {_day(slot.ends_on)}.",
        details=[("Product", slot.product.name), ("Slot", where),
                 ("Dates", f"{_day(slot.starts_on)} – {_day(slot.ends_on)}"),
                 ("Duration", f"{weeks} week{'s' if weeks != 1 else ''}"),
                 ("Amount paid", money(payment.amount, payment.currency)),
                 ("Payment ID", payment.razorpay_payment_id)],
        cta=("View your bookings", url("/dashboard/")),
        outro="Your ad goes live automatically on the start date. No further action is needed.")


def payment_failed(payment, reason=""):
    if payment.kind == "plan" and payment.plan:
        item, retry = f"{payment.plan.name} plan", ("Try again", url("/pricing/"))
    else:
        s = payment.ad_slot
        item = (f"Ad slot: {s.category.name if s.category else 'Home page'} · "
                f"{services.slot_label(s.slot_type, s.category, s.position)}") if s else "Ad slot booking"
        retry = ("Book again", url("/advertise/"))
    details = [("Item", item), ("Amount", money(payment.amount, payment.currency))]
    if reason:
        details.append(("Reason", reason))
    details.append(("Order ID", payment.razorpay_order_id))
    send_notification(
        payment.user.email, f"Payment failed: {item}", "Your payment didn't go through",
        f"We couldn't complete your payment for {item}. Nothing was activated on your account. "
        "If any amount was debited, your bank usually refunds it within 5–7 working days.",
        details=details, cta=retry, tone="bad",
        outro=f"Still stuck? Write to {settings.CONTACT_EMAIL} and include the order ID above.")



def password_reset(user, to, link):
    google_only = not user.has_usable_password()
    send_notification(
        to,
        "Set a Password for LetsPublic" if google_only else "Reset Your LetsPublic Password",
        "Set a password" if google_only else "Reset your password",
        (f"Your account ({user.username}) uses Google sign-in. Use this link to set a password, so you can also log in "
         "with your username. It works for 1 hour and only once."
         if google_only else
         f"We received a request to reset the password for {user.username}. This link works for 1 hour and can be used only once."),
        details=[("Username", user.username)],
        cta=("Choose a password" if google_only else "Choose a new password", link),
        outro="Didn't ask for this? Ignore this email and nothing changes.\n\nButton not working? Copy this link into your browser:\n" + link)


def password_changed(user):
    send_notification(
        user.email, "Your LetsPublic password was changed", "Password changed",
        "The password for your account was just changed.",
        details=[("Username", user.username), ("When", f"{timezone.localtime():%d %b %Y, %I:%M %p}")],
        cta=("Go to settings", url("/settings/")),
        outro=f"If this wasn't you, reset your password straight away and write to {settings.CONTACT_EMAIL}.")


def verify_email(user, link):
    name = services.display_name(user)
    send_notification(
        user.email, "Verify your LetsPublic email", "Confirm your email address",
        f"Hi {name}, thanks for joining LetsPublic. Confirm your email to activate your account. "
        f"This link works for {settings.EMAIL_VERIFY_HOURS} hours.",
        details=[("Username", user.username)],
        cta=("Verify my email", link),
        outro="Didn't create an account? Ignore this email and nothing happens.\n\n"
              "Button not working? Copy this link into your browser:\n" + link)