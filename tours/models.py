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


class TourCar(models.Model):
    name               = models.CharField(max_length=120, help_text="e.g. Mercedes S-Class")
    description        = models.CharField(max_length=255, blank=True, help_text="Short tagline shown on the card")
    image              = models.ImageField(upload_to="tour_cars/", blank=True, null=True, help_text="Car photo")
    max_passengers     = models.PositiveSmallIntegerField(default=4, help_text="Maximum passengers this vehicle seats")
    display_order      = models.PositiveSmallIntegerField(default=0, help_text="Lower = shown first")
    is_active          = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Tour Vehicle"
        verbose_name_plural = "Tour Vehicles"

    def __str__(self):
        return f"{self.name} (max {self.max_passengers} pax)"

    @property
    def image_url(self):
        if self.image:
            return self.image.url
        return None


class TourBooking(models.Model):
    """
    REPLACE your existing TourBooking with this schema.
    Key changes:
      - number_of_bags  → REMOVED
      - selected_car    → FK to TourCar (nullable for legacy rows)
      - paid / stripe_* → REMOVED (inquiry flow, no payment)
      - additional_stops → new JSON/text field
    """
    user                  = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="tour_bookings")
    tour_type             = models.CharField(max_length=60)
    passenger_name        = models.CharField(max_length=180)
    passenger_number      = models.CharField(max_length=40)
    passenger_email       = models.EmailField(blank=True)
    number_of_passengers  = models.PositiveSmallIntegerField(default=1)
    selected_car          = models.ForeignKey(
        TourCar,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="bookings",
        help_text="Vehicle chosen by the customer.",
    )
    pickup_address        = models.CharField(max_length=300)
    additional_stops      = models.TextField(blank=True, help_text="Newline-separated additional stops")
    booking_date          = models.DateField()
    booking_time          = models.TimeField()
    special_instruction   = models.TextField(blank=True, null=True)
    created_at            = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Tour Inquiry"
        verbose_name_plural = "Tour Inquiries"

    def __str__(self):
        return f"#{str(self.id).zfill(6)} — {self.passenger_name}"


