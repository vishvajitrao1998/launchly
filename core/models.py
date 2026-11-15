from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

User = settings.AUTH_USER_MODEL


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=8, default="🚀")
    color = models.CharField(max_length=7, default="#6366f1")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def live(self):
        """Approved AND its launch time (now or scheduled) has arrived."""
        return self.filter(status=Product.Status.APPROVED, launch_at__lte=timezone.now())


class Product(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        NEEDS_INFO = "needs_info", "Needs info"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    tagline = models.CharField(max_length=140)
    description = models.TextField()
    website_url = models.URLField()
    logo = models.ImageField(upload_to="logos/", blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    admin_note = models.TextField(blank=True, help_text="Message to the maker (shown on their dashboard / emailed).")
    is_premium = models.BooleanField(default=False)

    scheduled_for = models.DateTimeField(null=True, blank=True, help_text="Requested launch time.")
    launch_at = models.DateTimeField(null=True, blank=True, help_text="Set on approval; product is public once this passes.")

    upvote_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=["status", "launch_at"])]

    def __str__(self):
        return self.name

    @property
    def is_live(self):
        return self.status == self.Status.APPROVED and bool(self.launch_at) and self.launch_at <= timezone.now()

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:60] or "product"
            slug, n = base, 2
            while Product.objects.filter(slug=slug).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)


class Upvote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="upvotes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="uniq_upvote")]


class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="uniq_like")]


class Plan(models.Model):
    name = models.CharField(max_length=40)
    slug = models.SlugField(unique=True)
    tagline = models.CharField(max_length=120, blank=True)
    price_inr = models.PositiveIntegerField(default=0)
    price_usd = models.PositiveIntegerField(default=0)
    period_days = models.PositiveSmallIntegerField(default=30)
    premium_launches = models.PositiveSmallIntegerField(default=0, help_text="Premium-badge launches included per period.")
    features = models.JSONField(default=list)
    highlighted = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.name} (₹{self.price_inr})"


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    credits_left = models.PositiveSmallIntegerField(default=0)


class AdSlotQuerySet(models.QuerySet):
    def active_on(self, day):
        return self.filter(status=AdSlot.Status.ACTIVE, starts_on__lte=day, ends_on__gte=day)

    def held(self):
        """Paid slots + unpaid ones still inside the checkout hold window."""
        cutoff = timezone.now() - timedelta(minutes=settings.AD_HOLD_MINUTES)
        return self.filter(Q(status=AdSlot.Status.ACTIVE) | Q(status=AdSlot.Status.PENDING, created_at__gte=cutoff))


class AdSlot(models.Model):
    class Type(models.TextChoices):
        HERO = "hero", "Home hero banner"
        SPOTLIGHT = "spotlight", "Sponsored spotlight"
        CAT_FIRST = "cat_first", "Category list – 1st position"
        CAT_THIRD = "cat_third", "Category list – 3rd position"
        SIDEBAR = "sidebar", "Right sidebar"

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting payment"
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"

    slot_type = models.CharField(max_length=12, choices=Type.choices)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField(default=1)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="ad_slots")
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AdSlotQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=["slot_type", "category", "position", "starts_on", "ends_on"])]

    def __str__(self):
        return f"{self.get_slot_type_display()} · {self.product} ({self.starts_on}→{self.ends_on})"


class Payment(models.Model):
    class Kind(models.TextChoices):
        PLAN = "plan", "Plan"
        AD = "ad", "Ad slot"

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    kind = models.CharField(max_length=6, choices=Kind.choices)
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.SET_NULL)
    ad_slot = models.ForeignKey(AdSlot, null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    razorpay_order_id = models.CharField(max_length=64, unique=True)
    razorpay_payment_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.CREATED)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)



class ProductScreenshot(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="screenshots")
    image = models.ImageField(upload_to="screenshots/%Y/%m/")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
