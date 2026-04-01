from django.urls import path
from . import views

urlpatterns = [
    path("",                           views.tour_booking,      name="tours"),
    path("status/<int:booking_id>/",   views.tour_status,       name="tour_status"),
    path("cancelled/<int:booking_id>/",views.tour_cancelled,    name="tour_cancelled"),
    path("api/cars/",                  views.tour_cars_api,     name="tour_cars_api"),
]
