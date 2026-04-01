import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone


TOUR_TYPE_CHOICES = [
    ("yarra_valley",        "Yarra Valley Wine Tours"),
    ("mornington",          "Mornington Peninsula Wine Tours"),
    ("great_ocean_road",    "Great Ocean Road Tours"),
    ("victorian_winery",    "Victorian Winery Tours"),
    ("golf",                "Golf Tours"),
    ("melbourne_victorian", "Melbourne and Victorian Tours"),
    ("grampians",           "Grampians Tours"),
    ("peninsula_hot_springs", "Peninsula Hot Springs Tours"),
    ("fruit_picking",       "Fruit Picking Tours"),
    ("victorian_ski",       "Victorian Ski Tours"),
]


class TourBooking(models.Model):
    # Owner
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="tour_bookings",
    )

    # Tour type
    tour_type = models.CharField(max_length=30, choices=TOUR_TYPE_CHOICES, default="yarra_valley")

    # Passenger
    passenger_name   = models.CharField(max_length=200)
    passenger_number = models.CharField(max_length=30)
    passenger_email  = models.EmailField()

    # Trip details
    number_of_passengers = models.IntegerField(default=2)
    number_of_bags       = models.IntegerField(default=2)
    pickup_address       = models.CharField(max_length=500)
    booking_date         = models.DateField(default=datetime.date.today)
    booking_time         = models.TimeField(default=timezone.now)
    special_instruction  = models.TextField(null=True, blank=True)

    # Payment
    total_price              = models.DecimalField(max_digits=10, decimal_places=2)
    paid                     = models.BooleanField(default=False)
    stripe_payment_intent_id = models.CharField(max_length=200, blank=True)

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"TourBooking #{self.pk} [{self.get_tour_type_display()}] "
            f"— {self.passenger_name} ({self.booking_date})"
        )


class TourPrice(models.Model):
    """
    Admin-editable price for each tour type.
    One row per tour type. Create via Django admin.
    """
    tour_type = models.CharField(
        max_length=30,
        choices=TOUR_TYPE_CHOICES,
        unique=True,
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=250.00,
        help_text="Price per booking (AUD). Stripe 3% fee is added on top.",
    )
    price_note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional note shown to customer, e.g. 'per person' or 'per group up to 7'.",
    )

    class Meta:
        ordering = ["tour_type"]
        verbose_name = "Tour Price"
        verbose_name_plural = "Tour Prices"

    def __str__(self):
        return f"{self.get_tour_type_display()} — A${self.price}"
