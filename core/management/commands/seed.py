from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Category, Plan, Product
 
CATS = [("AI Tools", "🤖", "#8b5cf6"), ("Productivity", "⚡", "#6366f1"), ("Developer Tools", "🧑‍💻", "#0ea5e9"),
        ("Design", "🎨", "#ec4899"), ("Marketing", "📈", "#f59e0b"), ("Fintech", "💳", "#10b981")]

PLANS = [
    dict(slug="free", name="Starter", tagline="Launch your first product", price_inr=0, price_usd=0, premium_launches=0, order=1,
         features=["Unlimited standard launches", "Schedule launches ahead of time", "Upvotes, likes & maker profile", "Community support"]),
    dict(slug="pro", name="Pro", tagline="For makers who launch often", price_inr=999, price_usd=12, premium_launches=3, order=2, highlighted=True,
         features=["3 Premium launches / month", "Premium badge on your listing", "Priority review (within 24h)", "Schedule launches ahead of time", "Email support"]),
    dict(slug="scale", name="Scale", tagline="For studios & teams", price_inr=2499, price_usd=29, premium_launches=10, order=3,
         features=["10 Premium launches / month", "Premium badge on every launch", "Fastest review queue", "Launch analytics", "Priority support"]),
]

DEMO = [("Lumina AI", "Turn meeting notes into action items", "AI Tools", True), ("Taskwave", "Plan your week in one calm view", "Productivity", False),
        ("Shipkit", "Deploy any repo in 30 seconds", "Developer Tools", False), ("Palettify", "Brand palettes from a single prompt", "Design", True),
        ("Growthly", "Cold email that doesn't feel cold", "Marketing", False), ("Payloop", "Invoices that chase themselves", "Fintech", False),
        ("Promptly", "A shared prompt library for teams", "AI Tools", False), ("Focusbar", "A menu-bar timer that guards your deep work", "Productivity", False)]


class Command(BaseCommand):
    help = "Create demo categories, plans and sample products"

    def handle(self, *a, **k):
        for i, (n, icon, color) in enumerate(CATS):
            Category.objects.update_or_create(slug=n.lower().replace(" ", "-"), defaults=dict(name=n, icon=icon, color=color, order=i))
        for p in PLANS:
            Plan.objects.update_or_create(slug=p["slug"], defaults=p)
        maker, _ = get_user_model().objects.get_or_create(username="demo_maker", defaults={"email": "maker@example.com"})
        for n, tag, cat, prem in DEMO:
            Product.objects.get_or_create(name=n, defaults=dict(
                owner=maker, tagline=tag, description=f"{n} — {tag}. A demo listing created by the seed command.",
                website_url="https://example.com", category=Category.objects.get(name=cat), is_premium=prem,
                status="approved", launch_at=timezone.now(), upvote_count=len(n) * 3))
        self.stdout.write(self.style.SUCCESS("Seeded categories, plans and demo products."))
