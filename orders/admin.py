from django.contrib import admin
from .models import *

# Register your models here.
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    fields = (
        "user",
        "service_type",
        "passenger_name",
        "passenger_number", 
        "passenger_email",
        "number_of_passengers",
        "number_of_bags",
        "pickup_address",
        "destination_address",
        "additional_stop",
        "flight_number",
        "pickup_date",
        "pickup_time",
        "hourly_hours",
        "limo_service_type",
        "baby_seat",
        "number_of_babies",
        "baby_ages",
        "return_ride",
        "special_instruction",
        "vehicle_colour",
        "wedding_ribbon",
        "special_signboard",
        "total_price",
        "paid",
        "stripe_payment_intent_id",
        "driver_fee",
        "driver_name",
        "driver_number",
        "driver_email",
        "driver_address",
        "details_for_driver",
    )

admin.site.register(Discount)
admin.site.register(Rates)