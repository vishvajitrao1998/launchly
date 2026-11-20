from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import TemplateView
from . import api, payments, views, social,seo_views

from django.urls import path, reverse_lazy
from .forms import ResetRequestForm, ResetSetForm, LoginForm
from .ratelimit import by_field, ratelimit



login_view = auth_views.LoginView.as_view(authentication_form=LoginForm)
login_view = ratelimit("login-user", 8, 900, key=by_field("username"))(login_view)   # one account, many IPs
login_view = ratelimit("login-ip", 20, 900)(login_view)                                # one IP, many accounts

reset_view = auth_views.PasswordResetView.as_view(
    template_name="registration/password_reset_form.html", form_class=ResetRequestForm,
    success_url=reverse_lazy("password_reset_done"))
reset_view = ratelimit("reset-email", 3, 3600, key=by_field("email"))(reset_view)
reset_view = ratelimit("reset-ip", 10, 3600)(reset_view)

reset_confirm_view = auth_views.PasswordResetConfirmView.as_view(
    template_name="registration/password_reset_confirm.html", form_class=ResetSetForm,
    success_url=reverse_lazy("password_reset_complete"))
reset_confirm_view = ratelimit("reset-confirm", 20, 3600)(reset_confirm_view)


urlpatterns = [
    # pages
    path("", views.home, name="home"),
    path("pricing/", views.pricing, name="pricing"),
    path("advertise/", views.advertise, name="advertise"),
    path("launch-product/", views.submit, name="submit"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("review/", views.review, name="review"),
    path("product/<slug:slug>/", views.product_page, name="product"),
    path("login/", login_view, name="login"),
    path("auth/google/", social.google_login, name="google_login"),
    path("auth/google/callback/", social.google_callback, name="google_callback"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("top/", views.top_page, name="top"),
    path("products/", views.category_page, name="products"),
    path("category/<slug:slug>/", views.category_page, name="category"),
    path("billing/", views.billing_page, name="billing"),
    path("analytics/", views.analytics_page, name="analytics"),
    path("revenue/", views.revenue_page, name="revenue"),

    path("verify/sent/", views.verify_sent, name="verify_sent"),
    path("verify/resend/", views.resend_verification, name="verify_resend"),
    path("verify/<str:token>/", views.verify_email, name="verify_email"),

    # seo
    path("robots.txt", seo_views.robots_txt),
    path("sitemap.xml", seo_views.sitemap_xml),

    path("embed-code/", views.embed_page, name="embed_code"),
    path("embed/<slug:slug>/", views.embed_card, name="embed_card"),
    path("badge/<slug:slug>.svg", views.badge_svg, name="badge"),

    # pages
    path("settings/", views.settings_page, name="account"),
    path("p/about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
    path("p/contact/", TemplateView.as_view(template_name="pages/contact.html"), name="contact"),
    path("p/privacy/", TemplateView.as_view(template_name="pages/privacy.html"), name="privacy"),
    path("p/disclaimer/", TemplateView.as_view(template_name="pages/disclaimer.html"), name="disclaimer"),
    path("p/guide/", TemplateView.as_view(template_name="pages/guide.html"), name="guide"),

    # public API
    path("api/me/", api.me),
    path("api/categories/", api.categories),
    path("api/feed/", api.feed),
    path("api/products/", api.products),
    path("api/products/<int:pk>/upvote/", api.toggle_upvote),
    path("api/products/<int:pk>/like/", api.toggle_like),
    path("api/products/<slug:slug>/", api.product_detail),
    path("api/ads/board/", api.ad_board),
    path("api/pricing/", api.pricing),
    path("api/top/", api.top),
    path("api/rail/", api.rail),
    path("api/tags/", api.tags),

    # maker API
    path("api/me/products/", api.my_products),
    path("api/me/products/<int:pk>/", api.my_product),
    path("api/me/ads/", api.my_ads),

    # staff API
    path("api/admin/queue/", api.admin_queue),
    path("api/admin/products/<int:pk>/review/", api.admin_review),

    # payments
    path("api/payments/plan/", payments.buy_plan),
    path("api/payments/ad/", payments.book_ad),
    path("api/payments/verify/", payments.verify),
    path("razorpay/webhook/", payments.webhook),

    path("api/me/profile/", api.my_profile),
    path("api/me/password/", api.change_password),

    path("api/payments/failed/", payments.failed),

    # Billing

    path("api/me/billing/", api.billing),
    path("api/me/slots/", api.my_slots),
    path("api/me/payments/", api.my_payments),

    path("api/products/<int:pk>/track/", api.track),
    path("api/me/analytics/", api.analytics),

    # revenue analtics
    path("api/admin/revenue/", api.admin_revenue),
    path("api/admin/payments/", api.admin_payments),

    # Password change

    path("password-reset/", reset_view, name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", reset_confirm_view, name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
    template_name="registration/password_reset_complete.html"), name="password_reset_complete"),
]
