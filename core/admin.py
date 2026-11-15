from django.contrib import admin, messages

from . import services
from .models import AdSlot, Category, Like, Payment, Plan, Product, Subscription, Upvote, ProductScreenshot


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
    list_display = ("name", "price_inr", "price_usd", "premium_launches", "highlighted", "order")


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



admin.site.register(ProductScreenshot)
