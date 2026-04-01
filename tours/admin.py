from django.contrib import admin
from .models import TourCar, TourBooking

@admin.register(TourCar)
class TourCarAdmin(admin.ModelAdmin):
    list_display  = ['name', 'max_passengers', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active', 'max_passengers']
    ordering      = ['display_order', 'name']
    fields        = ['name', 'description', 'image', 'max_passengers', 'display_order', 'is_active']

@admin.register(TourBooking)
class TourBookingAdmin(admin.ModelAdmin):
    list_display  = ['id', 'passenger_name', 'tour_type', 'booking_date', 'selected_car', 'created_at']
    list_filter   = ['tour_type', 'booking_date', 'selected_car']
    search_fields = ['passenger_name', 'passenger_email', 'passenger_number', 'pickup_address']
    readonly_fields = ['created_at']
    raw_id_fields   = ['user', 'selected_car']
