"""Razorpay: create order -> Checkout in browser -> verify signature (+ webhook as safety net)."""
import json
import time
from datetime import timedelta

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import AdSlot, Category, Payment, Plan, Product


def rz_client():
    import razorpay
    if not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
        raise RuntimeError("Razorpay keys are not configured. Set RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET in .env")
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def _checkout(user, kind, amount, currency, description, **fk):
    try:
        order = rz_client().order.create({
            "amount": amount * 100, "currency": currency,   # paise / cents
            "receipt": f"{kind}-{user.id}-{int(time.time())}", "notes": {"user": user.id, "kind": kind}})
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Razorpay could not create the order: {e}")
    Payment.objects.create(user=user, kind=kind, amount=amount, currency=currency,
                           razorpay_order_id=order["id"], **fk)
    return {"key": settings.RAZORPAY_KEY_ID, "amount": amount * 100, "currency": currency,
            "order_id": order["id"], "name": "Launchly", "description": description,
            "prefill": {"name": user.get_full_name() or user.username, "email": user.email}}


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def buy_plan(request):
    plan = get_object_or_404(Plan, slug=request.data.get("plan"))
    cur = services.get_currency(request)
    price = services.plan_price(plan, cur)
    if price <= 0:
        return Response({"detail": "This plan is free."}, status=400)
    try:
        return Response({"checkout": _checkout(request.user, "plan", price, cur, f"{plan.name} plan", plan=plan)})
    except RuntimeError as e:
        return Response({"detail": str(e)}, status=503)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def book_ad(request):
    d = request.data
    slot_type = d.get("slot_type")
    cur = services.get_currency(request)
    if slot_type not in settings.AD_PRICING:
        return Response({"detail": "Unknown slot."}, status=400)
    category = None
    if slot_type in ("cat_first", "cat_third"):
        category = get_object_or_404(Category, slug=d.get("category"))
        max_pos = {"spotlight": 3, "sidebar": 2}.get(slot_type, 1)
    try:
        position = int(d.get("position") or 1) if max_pos > 1 else 1
    except ValueError:
        position = 0
    if not 1 <= position <= max_pos:
        return Response({"detail": f"Position must be between 1 and {max_pos}."}, status=400)

    try:
        product_id = int(d.get("product"))
    except (TypeError, ValueError):
        return Response({"detail": "Choose a product."}, status=400)
    product = get_object_or_404(Product, pk=product_id, owner=request.user, status=Product.Status.APPROVED)
    start = parse_date(str(d.get("start_date")))
    try:
        weeks = int(d.get("weeks"))
    except (TypeError, ValueError):
        weeks = 0
    if not start or start < timezone.localdate() or not 1 <= weeks <= 12:
        return Response({"detail": "Choose a valid start date and 1-12 weeks."}, status=400)
    end = start + timedelta(days=weeks * 7 - 1)

    if services.slot_taken(slot_type, category.id if category else None, position, start, end):
        return Response({"detail": "That slot is already booked for the selected dates."}, status=409)

    amount = services.slot_price(slot_type, cur) * weeks
    slot = AdSlot.objects.create(slot_type=slot_type, category=category, position=position,
                                 product=product, starts_on=start, ends_on=end)
    try:
        checkout = _checkout(request.user, "ad", amount,cur,
                             f"{services.slot_label(slot_type, category, position)} × {weeks}w", ad_slot=slot)

    except RuntimeError as e:
        slot.delete()
        return Response({"detail": str(e)}, status=503)
    return Response({"checkout": checkout})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify(request):
    import razorpay
    d = request.data
    payment = get_object_or_404(Payment, razorpay_order_id=d.get("razorpay_order_id"), user=request.user)
    try:
        rz_client().utility.verify_payment_signature({
            "razorpay_order_id": d.get("razorpay_order_id"),
            "razorpay_payment_id": d.get("razorpay_payment_id"),
            "razorpay_signature": d.get("razorpay_signature")})
    except razorpay.errors.SignatureVerificationError:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        return Response({"detail": "Payment signature mismatch."}, status=400)
    services.fulfil_payment(payment, d.get("razorpay_payment_id", ""))
    return Response({"ok": True, "kind": payment.kind})


@csrf_exempt
@require_POST
def webhook(request):
    """Configure in Razorpay Dashboard -> Webhooks: events payment.captured / order.paid."""
    try:
        rz_client().utility.verify_webhook_signature(
            request.body.decode(), request.headers.get("X-Razorpay-Signature", ""), settings.RAZORPAY_WEBHOOK_SECRET)
    except Exception:
        return HttpResponse(status=400)
    event = json.loads(request.body)
    if event.get("event") in ("payment.captured", "order.paid"):
        ent = event["payload"]["payment"]["entity"]
        payment = Payment.objects.filter(razorpay_order_id=ent.get("order_id")).first()
        if payment:
            services.fulfil_payment(payment, ent["id"])
    return HttpResponse("ok")
