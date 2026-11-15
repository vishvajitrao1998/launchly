from django.contrib.auth import views as auth_views
from django.urls import path

from . import api, payments, views

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
]
