from django.contrib import admin, messages

from . import services
from .models import AdSlot, Category, Like, Payment, Plan, Product, Subscription, Upvote, ProductScreenshot, Profile,ProductStat, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "uses")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    actions = ["ban", "allow"]

    @admin.display(description="Products")
    def uses(self, obj):
        return obj.products.count()

    @admin.action(description="🚫 Ban selected tags")
    def ban(self, request, qs):
        qs.update(is_active=False)

    @admin.action(description="✅ Allow selected tags")
    def allow(self, request, qs):
        qs.update(is_active=True)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "email_verified", "google_id")
    list_filter = ("email_verified",)
    search_fields = ("user__username", "user__email")
    actions = ["mark_verified"]

    @admin.action(description="✅ Mark email as verified")
    def mark_verified(self, request, qs):
        qs.update(email_verified=True)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "color", "order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "category", "status", "is_premium", "scheduled_for", "launch_at", "upvote_count")
    list_filter = ("status", "is_premium", "category")
    search_fields = ("name", "owner__email", "owner__username")
    readonly_fields = ("upvote_count", "like_count", "created_at", "updated_at")
    actions = ["approve", "reject", "request_info", "email_user"]
    filter_horizontal = ("tags",)

    def _run(self, request, qs, action, need_note):
        done = 0
        for p in qs:
            if need_note and not p.admin_note.strip():
                self.message_user(request, f"'{p.name}': fill in the Admin note first.", messages.WARNING)
                continue
            services.review_product(p, action, p.admin_note)
            done += 1
        self.message_user(request, f"{done} product(s) updated and the maker was emailed.")

    @admin.action(description="✅ Approve (and email maker)")
    def approve(self, request, qs):
        self._run(request, qs, "approve", False)

    @admin.action(description="⛔ Reject (reason = Admin note)")
    def reject(self, request, qs):
        self._run(request, qs, "reject", False)

    @admin.action(description="📝 Request more info (message = Admin note)")
    def request_info(self, request, qs):
        self._run(request, qs, "request_info", True)

    @admin.action(description="✉️ Email maker (message = Admin note)")
    def email_user(self, request, qs):
        self._run(request, qs, "email", True)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price_inr", "price_usd", "premium_launches", "has_social_links","highlighted", "order")


@admin.register(AdSlot)
class AdSlotAdmin(admin.ModelAdmin):
    list_display = ("slot_type", "category", "position", "product", "starts_on", "ends_on", "status")
    list_filter = ("slot_type", "status", "category")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("razorpay_order_id", "user", "kind", "amount", "currency", "status", "created_at")
    list_filter = ("kind", "status")
    readonly_fields = [f.name for f in Payment._meta.fields]


admin.site.register([Subscription, Upvote, Like])


admin.site.register(ProductStat)
admin.site.register(ProductScreenshot)
