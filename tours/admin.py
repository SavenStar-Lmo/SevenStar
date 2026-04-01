from django.contrib import admin
from .models import TourBooking, TourPrice, TOUR_TYPE_CHOICES


@admin.register(TourPrice)
class TourPriceAdmin(admin.ModelAdmin):
    list_display  = ("get_tour_type_display", "price", "price_note")
    ordering      = ("tour_type",)

    def get_tour_type_display(self, obj):
        return obj.get_tour_type_display()
    get_tour_type_display.short_description = "Tour"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Pre-seed all tour types on first visit so admin sees them all
        return form

    def changelist_view(self, request, extra_context=None):
        # Auto-create missing TourPrice rows so admin always sees all 10 tours
        existing_keys = set(TourPrice.objects.values_list("tour_type", flat=True))
        missing = [
            TourPrice(tour_type=k)
            for k, _ in TOUR_TYPE_CHOICES
            if k not in existing_keys
        ]
        if missing:
            TourPrice.objects.bulk_create(missing)
        return super().changelist_view(request, extra_context)


@admin.register(TourBooking)
class TourBookingAdmin(admin.ModelAdmin):
    list_display  = (
        "id", "passenger_name", "tour_type", "booking_date",
        "number_of_passengers", "total_price", "paid", "created_at",
    )
    list_filter   = ("tour_type", "paid", "booking_date")
    search_fields = ("passenger_name", "passenger_email", "passenger_number", "pickup_address")
    readonly_fields = (
        "stripe_payment_intent_id", "created_at", "total_price",
    )
    ordering      = ("-created_at",)

    fieldsets = (
        ("Booking Info", {
            "fields": ("user", "tour_type", "booking_date", "booking_time"),
        }),
        ("Passenger", {
            "fields": ("passenger_name", "passenger_number", "passenger_email"),
        }),
        ("Trip Details", {
            "fields": (
                "pickup_address", "number_of_passengers",
                "number_of_bags", "special_instruction",
            ),
        }),
        ("Payment", {
            "fields": ("total_price", "paid", "stripe_payment_intent_id"),
        }),
        ("Meta", {
            "fields": ("created_at",),
        }),
    )
