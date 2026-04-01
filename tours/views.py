import datetime
import json
import logging
import urllib.parse

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .models import TOUR_TYPE_CHOICES, TourBooking, TourCar

logger = logging.getLogger(__name__)

WHATSAPP_NUMBER = "61483841489"  # E.164 without + for wa.me link


# ─────────────────────────────────────────────────────────────────────────────
# Tour catalogue  (static metadata — no prices)
# ─────────────────────────────────────────────────────────────────────────────

TOUR_CATALOGUE = {
    "yarra_valley": {
        "label":   "Yarra Valley Wine Tours",
        "emoji":   "🍷",
        "tagline": "Sip your way through Victoria's most celebrated wine country.",
        "about":   (
            "The Yarra Valley is home to more than 80 cellar doors set against dramatic "
            "mountain backdrops and lush green valleys. Famous for cool-climate Pinot Noir, "
            "Chardonnay, and world-class sparkling wines, it is just an hour from Melbourne CBD. "
            "Our knowledgeable drivers take you on a carefully curated route visiting boutique "
            "wineries, artisan producers, and gourmet providores at a relaxed, unhurried pace."
        ),
        "highlights": [
            "Tours through the Yarra Valley's best wineries.",
            "Stunning cool-climate wines and gourmet food.",
            "Friendly and knowledgeable winery tour drivers.",
            "Personalised, flexible service.",
            "Drinks and music of your choice.",
            "Intimate couples' tours and larger group packages.",
        ],
        "image": "img/tours/yarra_valley.jpg",
    },
    "mornington": {
        "label":   "Mornington Peninsula Wine Tours",
        "emoji":   "🌊",
        "tagline": "Ocean breezes, rolling vines, and exceptional Pinot — just 90 minutes from Melbourne.",
        "about":   (
            "The Mornington Peninsula is Victoria's most scenic wine destination, stretching "
            "between Port Phillip Bay and Western Port Bay. Celebrated for its maritime-influenced "
            "Pinot Noir and Chardonnay, the region also boasts artisan breweries, farm-gate "
            "producers, and stunning coastal lookouts."
        ),
        "highlights": [
            "Curated visits to the Peninsula's finest cellar doors.",
            "World-renowned Pinot Noir and Chardonnay tastings.",
            "Scenic coastal and hinterland routes.",
            "Expert local guides who know every hidden gem.",
            "Gourmet lunch stops at award-winning restaurants.",
            "Private and group tour options available.",
        ],
        "image": "img/tours/mornington.jpg",
    },
    "great_ocean_road": {
        "label":   "Great Ocean Road Tours",
        "emoji":   "🌊",
        "tagline": "One of the world's great coastal drives — experienced in complete luxury.",
        "about":   (
            "The Great Ocean Road is one of Australia's most iconic journeys, hugging the "
            "spectacular surf coast and passing through the Otway Ranges before revealing the "
            "breathtaking Twelve Apostles limestone stacks."
        ),
        "highlights": [
            "Private chauffeur-driven tours — no bus crowds.",
            "The iconic Twelve Apostles, Loch Ard Gorge, and London Arch.",
            "Otway Rainforest walks and Cape Otway Lighthouse.",
            "Flexible itinerary — stop wherever you choose.",
            "Koala and wildlife spotting en route.",
            "Full-day and sunrise/sunset tour options.",
        ],
        "image": "img/tours/great_ocean_road.jpg",
    },
    "victorian_winery": {
        "label":   "Victorian Winery Tours",
        "emoji":   "🍇",
        "tagline": "Explore Victoria's diverse wine regions beyond the usual tourist trail.",
        "about":   (
            "Victoria is Australia's most diverse wine state, with over a dozen distinct wine "
            "regions from the alpine valleys of the northeast to the warm Heathcote plains."
        ),
        "highlights": [
            "Tailor-made itineraries across multiple Victorian wine regions.",
            "Boutique cellar doors not found on mainstream tours.",
            "Knowledgeable drivers passionate about Victorian wine.",
            "Paired tastings with artisan cheese and charcuterie.",
            "Overnight multi-day regional tour packages available.",
            "Intimate groups and corporate events welcome.",
        ],
        "image": "img/tours/victorian_winery.jpg",
    },
    "golf": {
        "label":   "Golf Tours",
        "emoji":   "⛳",
        "tagline": "Play Victoria's finest courses — we handle the driving, you handle the birdies.",
        "about":   (
            "Victoria is home to some of Australia's most prestigious golf courses, from the "
            "Sandbelt's celebrated links to the spectacular clifftop fairways of the Mornington Peninsula."
        ),
        "highlights": [
            "Door-to-door transfers to Victoria's top golf courses.",
            "Ample luggage and golf bag storage in all vehicles.",
            "Multi-course day packages across the Melbourne Sandbelt.",
            "Corporate golf day coordination and group transport.",
            "Refreshments and music of your choice en route.",
            "Sunrise tee-time pickups — we're always on schedule.",
        ],
        "image": "img/tours/golf.jpg",
    },
    "melbourne_victorian": {
        "label":   "Melbourne and Victorian Tours",
        "emoji":   "🏙️",
        "tagline": "Discover the soul of Melbourne and Victoria's most extraordinary attractions.",
        "about":   (
            "From Melbourne's world-famous laneways, galleries, and food scene to the wider "
            "wonders of Victoria — the Dandenong Ranges, Phillip Island, Healesville Sanctuary."
        ),
        "highlights": [
            "Customised Melbourne city tours and hidden laneway experiences.",
            "Phillip Island penguin parade transfers and tours.",
            "Dandenong Ranges and Healesville Sanctuary day trips.",
            "Goldfields and historic town itineraries.",
            "Flexible half-day, full-day, and multi-day options.",
            "Expert local commentary throughout your journey.",
        ],
        "image": "img/tours/melbourne.jpg",
    },
    "grampians": {
        "label":   "Grampians Tours",
        "emoji":   "🏔️",
        "tagline": "Ancient sandstone ranges, Aboriginal rock art, and breathtaking panoramas.",
        "about":   (
            "The Grampians National Park is one of Victoria's most spectacular natural landscapes, "
            "featuring dramatic sandstone mountain ranges, stunning waterfalls, and abundant wildlife."
        ),
        "highlights": [
            "Private chauffeur transfers from Melbourne to the Grampians.",
            "MacKenzie Falls, Pinnacle Lookout, and Boroka Lookout.",
            "Aboriginal rock art sites with cultural context.",
            "Wildlife encounters — kangaroos, emus, and koalas.",
            "Grampians wineries and Halls Gap dining.",
            "Overnight and two-day itinerary packages available.",
        ],
        "image": "img/tours/grampians.jpg",
    },
    "peninsula_hot_springs": {
        "label":   "Peninsula Hot Springs Tours",
        "emoji":   "♨️",
        "tagline": "Soak, relax, and rejuvenate — arrive and depart in complete luxury.",
        "about":   (
            "Peninsula Hot Springs is Australia's premier bathing and spa destination, set across "
            "65 acres of natural thermal landscape on the Mornington Peninsula."
        ),
        "highlights": [
            "Return chauffeur transfers from Melbourne to Peninsula Hot Springs.",
            "Flexible departure times to suit your session booking.",
            "Combine with Mornington Peninsula wine tour on the same day.",
            "Comfortable, spacious vehicles perfect post-spa.",
            "Optional scenic coastal route through Frankston and Dromana.",
            "Group bookings and hen's party packages welcome.",
        ],
        "image": "img/tours/hot_springs.jpg",
    },
    "fruit_picking": {
        "label":   "Fruit Picking Tours",
        "emoji":   "🍓",
        "tagline": "From vine to basket — a fresh, family-friendly Victorian farm experience.",
        "about":   (
            "Victoria's fertile valleys and orchards produce some of Australia's finest stone "
            "fruits, berries, and tree fruits."
        ),
        "highlights": [
            "Family-friendly farm tours in Victoria's best fruit-growing regions.",
            "Seasonal availability — strawberries, cherries, apples, and berries.",
            "Yarra Valley and Wandin orchard visits.",
            "Combine with winery or distillery stops for adults.",
            "All ages welcome — great for school holidays.",
            "Relaxed, flexible pace with knowledgeable drivers.",
        ],
        "image": "img/tours/fruit_picking.jpg",
    },
    "victorian_ski": {
        "label":   "Victorian Ski Tours",
        "emoji":   "⛷️",
        "tagline": "Hit the slopes stress-free — we handle the alpine roads so you don't have to.",
        "about":   (
            "Victoria's alpine resorts — Mount Buller, Falls Creek, Mount Hotham, and Lake Mountain "
            "— offer spectacular skiing and snowboarding from June to September."
        ),
        "highlights": [
            "Transfers to Mount Buller, Falls Creek, Hotham, and Lake Mountain.",
            "Ample ski bag and equipment storage in every vehicle.",
            "Early morning departures to maximise your time on the snow.",
            "Return transfers — no driving tired alpine roads at night.",
            "Group bookings and family ski trip packages.",
            "Season pass holders and day-trippers equally welcome.",
        ],
        "image": "img/tours/ski.jpg",
    },
}

TOUR_LIST = [{"key": k, **v} for k, v in TOUR_CATALOGUE.items()]


# ─────────────────────────────────────────────────────────────────────────────
# API: return cars as JSON (for dynamic passenger cap)
# ─────────────────────────────────────────────────────────────────────────────

@require_GET
def tour_cars_api(request):
    cars = TourCar.objects.filter(is_active=True).values(
        "id", "name", "description", "max_passengers", "display_order"
    )
    data = []
    for c in cars:
        data.append({
            "id":             c["id"],
            "name":           c["name"],
            "description":    c["description"],
            "max_passengers": c["max_passengers"],
        })
    return JsonResponse({"cars": data})


# ─────────────────────────────────────────────────────────────────────────────
# Main booking view
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def tour_booking(request):
    valid_keys = {k for k, _ in TOUR_TYPE_CHOICES}
    raw_type   = request.GET.get("type", request.POST.get("tour_type", "")).lower().strip()

    # ── No type → tour selection page ────────────────────────────────────────
    if not raw_type or raw_type not in valid_keys:
        return render(request, "tours/tour_select.html", {
            "tours": TOUR_LIST,
        })

    tour_key  = raw_type
    tour_info = TOUR_CATALOGUE[tour_key]
    cars      = list(TourCar.objects.filter(is_active=True).order_by("display_order", "name"))

    # Prefill from user profile
    prefill_email = request.user.email or ""
    prefill_phone = ""
    try:
        prefill_phone = request.user.extended_profile.phone or ""
    except AttributeError:
        pass

    # ── POST ─────────────────────────────────────────────────────────────────
    if request.method == "POST":
        passenger_name   = request.POST.get("passenger_name", "").strip()
        passenger_number = request.POST.get("passenger_number", "").strip()
        passenger_email  = request.POST.get("passenger_email", "").strip()
        pickup_address   = request.POST.get("pickup_address", "").strip()
        booking_date_raw = request.POST.get("booking_date", "").strip()
        booking_time_raw = request.POST.get("booking_time", "").strip()
        num_passengers   = int(request.POST.get("number_of_passengers", 1))
        car_id           = request.POST.get("selected_car", "").strip()
        instructions     = request.POST.get("special_instruction", "").strip()

        # Additional stops — submitted as multiple inputs named "stop[]"
        raw_stops   = request.POST.getlist("stop[]")
        extra_stops = [s.strip() for s in raw_stops if s.strip()]
        stops_text  = "\n".join(extra_stops)

        def form_error(msg):
            return render(request, "tours/tour_booking_form.html", {
                "error":      msg,
                "tour_key":   tour_key,
                "tour":       tour_info,
                "cars":       cars,
                "form_data": {
                    "passenger_name":      passenger_name,
                    "passenger_number":    passenger_number,
                    "passenger_email":     passenger_email,
                    "pickup_address":      pickup_address,
                    "booking_date":        booking_date_raw,
                    "booking_time":        booking_time_raw,
                    "number_of_passengers": num_passengers,
                    "selected_car":        car_id,
                    "special_instruction": instructions,
                    "stops":               extra_stops,
                },
                "google_maps_key": settings.GOOGLE_MAPS_API_KEY,
            })

        # Validate required fields
        if not passenger_name:
            return form_error("Please enter your full name.")
        if not passenger_number:
            return form_error("Please enter your phone number.")
        if not passenger_email:
            return form_error("Please enter your email address.")
        if not pickup_address:
            return form_error("Please enter your pickup address.")
        if not booking_date_raw:
            return form_error("Please select a tour date.")
        if not booking_time_raw:
            return form_error("Please select a pickup time.")

        # Validate car & passenger cap
        selected_car_obj = None
        if car_id:
            try:
                selected_car_obj = TourCar.objects.get(id=car_id, is_active=True)
                if num_passengers > selected_car_obj.max_passengers:
                    return form_error(
                        f"The {selected_car_obj.name} seats a maximum of "
                        f"{selected_car_obj.max_passengers} passenger(s). "
                        f"Please select a larger vehicle or reduce passengers."
                    )
            except TourCar.DoesNotExist:
                return form_error("Invalid vehicle selected. Please choose from the list.")

        try:
            booking_date = datetime.date.fromisoformat(booking_date_raw)
        except ValueError:
            return form_error("Invalid date format.")

        try:
            h, m = booking_time_raw.split(":")
            booking_time = datetime.time(int(h), int(m))
        except (ValueError, AttributeError):
            booking_time = datetime.time(8, 0)

        # Save the inquiry
        try:
            booking = TourBooking.objects.create(
                user=request.user,
                tour_type=tour_key,
                passenger_name=passenger_name,
                passenger_number=passenger_number,
                passenger_email=passenger_email,
                number_of_passengers=num_passengers,
                selected_car=selected_car_obj,
                pickup_address=pickup_address,
                additional_stops=stops_text,
                booking_date=booking_date,
                booking_time=booking_time,
                special_instruction=instructions or None,
            )
        except Exception as exc:
            return form_error(f"Could not save your inquiry: {exc}")

        # Build WhatsApp message
        tour_label   = tour_info["label"]
        car_name     = selected_car_obj.name if selected_car_obj else "Not specified"
        stops_line   = ""
        if extra_stops:
            stops_formatted = "\n".join([f"  • {s}" for s in extra_stops])
            stops_line = f"\n📍 Additional Stops:\n{stops_formatted}"

        wa_message = (
            f"🌟 *SevenStar Limo — Tour Inquiry*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Reference: #{str(booking.id).zfill(6)}\n"
            f"🗺️ Tour: {tour_label}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Name: {passenger_name}\n"
            f"📞 Phone: {passenger_number}\n"
            f"✉️ Email: {passenger_email}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚗 Vehicle: {car_name}\n"
            f"👥 Passengers: {num_passengers}\n"
            f"📍 Pickup: {pickup_address}"
            f"{stops_line}\n"
            f"📅 Date: {booking_date_raw}\n"
            f"⏰ Time: {booking_time_raw}\n"
        )
        if instructions:
            wa_message += f"📝 Notes: {instructions}\n"
        wa_message += f"━━━━━━━━━━━━━━━━━━━━━\n"
        wa_message += f"I'd like to inquire about this tour. Please confirm availability."

        wa_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(wa_message)}"

        return render(request, "tours/tour_whatsapp_redirect.html", {
            "booking":    booking,
            "tour_info":  tour_info,
            "wa_url":     wa_url,
        })

    # ── GET ───────────────────────────────────────────────────────────────────
    form_data = {
        "passenger_email":      prefill_email,
        "passenger_number":     prefill_phone,
        "booking_date":         str(datetime.date.today()),
        "number_of_passengers": 2,
    }

    return render(request, "tours/tour_booking_form.html", {
        "tour_key":        tour_key,
        "tour":            tour_info,
        "cars":            cars,
        "form_data":       form_data,
        "google_maps_key": settings.GOOGLE_MAPS_API_KEY,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Status / confirmation views  (kept for legacy bookings / direct URL access)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def tour_status(request, booking_id):
    booking   = get_object_or_404(TourBooking, id=booking_id, user=request.user)
    tour_info = TOUR_CATALOGUE.get(booking.tour_type, {})

    # For the inquiry flow, a saved booking is always "confirmed"
    return render(request, "tours/tour_confirmed.html", {
        "booking":   booking,
        "tour_info": tour_info,
    })


@login_required
def tour_cancelled(request, booking_id):
    booking   = get_object_or_404(TourBooking, id=booking_id, user=request.user)
    tour_info = TOUR_CATALOGUE.get(booking.tour_type, {})
    return render(request, "tours/tour_cancelled.html", {
        "booking":   booking,
        "tour_info": tour_info,
    })
