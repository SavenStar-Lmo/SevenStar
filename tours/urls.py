from django.urls import path
from . import views

urlpatterns = [
    path("",                          views.tour_booking,  name="tours"),
    path("status/<int:booking_id>/",  views.tour_status,   name="tour_status"),
    path("stripe/webhook/",           views.tour_stripe_webhook, name="tour_stripe_webhook"),
]
