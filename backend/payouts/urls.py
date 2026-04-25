from django.urls import path

from . import views

urlpatterns = [
    path("merchants/", views.merchant_list, name="merchant-list"),
    path("merchants/<uuid:merchant_id>/", views.merchant_detail, name="merchant-detail"),
    path(
        "merchants/<uuid:merchant_id>/ledger/",
        views.merchant_ledger,
        name="merchant-ledger",
    ),
    path("merchants/<uuid:merchant_id>/payouts/", views.payout_list, name="payout-list"),
    path(
        "merchants/<uuid:merchant_id>/payouts/create/",
        views.create_payout,
        name="create-payout",
    ),
    path(
        "merchants/<uuid:merchant_id>/payouts/<uuid:payout_id>/",
        views.payout_detail,
        name="payout-detail",
    ),
]
