from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import TemplateView
from . import api, payments, views

from django.urls import path, reverse_lazy
from .forms import ResetRequestForm, ResetSetForm

urlpatterns = [
    # pages
    path("", views.home, name="home"),
    path("pricing/", views.pricing, name="pricing"),
    path("advertise/", views.advertise, name="advertise"),
    path("launch-product/", views.submit, name="submit"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("review/", views.review, name="review"),
    path("product/<slug:slug>/", views.product_page, name="product"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("top/", views.top_page, name="top"),
    path("products/", views.category_page, name="products"),
    path("category/<slug:slug>/", views.category_page, name="category"),
    path("billing/", views.billing_page, name="billing"),
    path("analytics/", views.analytics_page, name="analytics"),
    

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

    # Password change

    path("password-reset/", auth_views.PasswordResetView.as_view(
    template_name="registration/password_reset_form.html", form_class=ResetRequestForm,
    success_url=reverse_lazy("password_reset_done")), name="password_reset"),
path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
    template_name="registration/password_reset_done.html"), name="password_reset_done"),
path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
    template_name="registration/password_reset_confirm.html", form_class=ResetSetForm,
    success_url=reverse_lazy("password_reset_complete")), name="password_reset_confirm"),
path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
    template_name="registration/password_reset_complete.html"), name="password_reset_complete"),
]
