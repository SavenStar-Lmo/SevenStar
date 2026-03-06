import time
import datetime
import logging
import requests
import stripe
import googlemaps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Discount, Order, Rates

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Service type configuration  (structure is static, prices come from DB)
# ─────────────────────────────────────────────────────────────────────────────

MELBOURNE_AIRPORT = "Melbourne Airport"

SERVICE_TYPES = {
    "ptp": {
        "label": "Point to Point",
        "show_destination": True,
        "show_flight": False,
        "lock_pickup": None,
        "lock_destination": None,
        "flat": False,
    },
    "oh": {
        "label": "1 Hour / As Directed",
        "show_destination": False,
        "show_flight": False,
        "lock_pickup": None,
        "lock_destination": None,
        "flat": True,
    },
    "th": {
        "label": "2 Hour Hire",
        "show_destination": False,
        "show_flight": False,
        "lock_pickup": None,
        "lock_destination": None,
        "flat": True,
    },
    "fair": {
        "label": "From Airport",
        "show_destination": True,
        "show_flight": True,
        "lock_pickup": MELBOURNE_AIRPORT,
        "lock_destination": None,
        "flat": False,
    },
    "tair": {
        "label": "To Airport",
        "show_destination": True,
        "show_flight": True,
        "lock_pickup": None,
        "lock_destination": MELBOURNE_AIRPORT,
        "flat": False,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_rates():
    """
    Fetch all Rates rows from DB ordered cheapest → most expensive.
    Returns a list of plain dicts so views/templates don't touch ORM objects.
    Falls back to hardcoded defaults if the table is empty.
    """
    qs = Rates.objects.all().order_by("base_price")
    if qs.exists():
        return [
            {
                "name":           r.name,
                "max_passengers": r.max_passangers,
                "max_bags":       r.max_bags,
                "base_price":     float(r.base_price),
                "per_km":         float(r.per_km_rate),
                "stop":           float(r.stop),
                "th_rate":        float(r.th_rate),
                "oh_rate":        float(r.oh_rate),
            }
            for r in qs
        ]
    # Fallback so the site never breaks on an empty DB
    return [
        {"name": "Sedan 1-5",    "max_passengers": 5,  "max_bags": 5,  "base_price": 30.00,  "per_km": 3.50, "stop": 15.00, "th_rate": 200.00, "oh_rate": 100.00},
        {"name": "SUV 1-7",      "max_passengers": 7,  "max_bags": 7,  "base_price": 55.00,  "per_km": 5.50, "stop": 25.00, "th_rate": 250.00, "oh_rate": 125.00},
        {"name": "Stretch 1-13", "max_passengers": 13, "max_bags": 13, "base_price": 135.00, "per_km": 9.50, "stop": 65.00, "th_rate": 300.00, "oh_rate": 150.00},
    ]


def _get_discounts():
    """
    Returns (th_discount, return_discount) as floats.
    Uses Discount.objects.first() as instructed; falls back to defaults.
    """
    disc = Discount.objects.first()
    if disc:
        return float(disc.th_discount), float(disc.return_discount)
    return 0.025, 0.05


def _find_rate(rates, vehicle_name):
    """Find a rate dict by vehicle name; fall back to cheapest if not found."""
    for r in rates:
        if r["name"] == vehicle_name:
            return r
    return rates[0]


# ─────────────────────────────────────────────────────────────────────────────
# Helper 1 – Distance (Google Maps — active)
# ─────────────────────────────────────────────────────────────────────────────

# def calculate_distance(pickup: str, destination: str, extra_stop: str | None) -> dict:
#     """
#     Uses Google Maps Directions API to calculate driving distance.
#     Returns distance_km and has_tolls.
#     """
#     gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
# 
#     waypoints = [extra_stop] if extra_stop else None
# 
#     directions = gmaps.directions(
#         origin=pickup,
#         destination=destination,
#         waypoints=waypoints,
#         mode="driving",
#         optimize_waypoints=False,
#     )
# 
#     if not directions:
#         raise ValueError("Google Maps returned no route for the given addresses.")
# 
#     total_meters = sum(leg["distance"]["value"] for leg in directions[0]["legs"])
#     distance_km  = round(total_meters / 1000, 2)
# 
#     has_tolls = any(
#         "toll" in step.get("html_instructions", "").lower()
#         for leg in directions[0]["legs"]
#         for step in leg["steps"]
#     )
# 
#     return {
#         "distance_km": distance_km,
#         "has_tolls":   has_tolls,
#     }


# ─────────────────────────────────────────────────────────────────────────────
# Helper 1 (alt) – Distance via Mapbox (commented out / backup)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_distance(pickup: str, destination: str, extra_stop: str | None) -> dict:

    def get_coords(address):
        """Geocode an address string → (latitude, longitude) via Nominatim."""
        url = "https://nominatim.openstreetmap.org/search"
        resp = requests.get(
            url,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "MelbourneChauffeurApp/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            raise ValueError("Address not found: {}".format(address))
        return float(data[0]["lat"]), float(data[0]["lon"])  # (lat, lng)

    try:
        # 1. Geocode all points
        p1 = get_coords(pickup)
        p2 = get_coords(destination)

        # Build coordinate string for OSRM: lng,lat pairs separated by semicolons
        coords_list = ["{},{}".format(p1[1], p1[0])]
        if extra_stop:
            ps = get_coords(extra_stop)
            coords_list.append("{},{}".format(ps[1], ps[0]))
        coords_list.append("{},{}".format(p2[1], p2[0]))
        coordinates = ";".join(coords_list)

        # 2. Get driving directions via OSRM
        route_url = "https://router.project-osrm.org/route/v1/driving/{}".format(coordinates)
        route_resp = requests.get(
            route_url,
            params={"overview": "false"},
            headers={"User-Agent": "MelbourneChauffeurApp/1.0"},
            timeout=10,
        )
        route_resp.raise_for_status()
        route_data = route_resp.json()

        if route_data.get("code") != "Ok" or not route_data.get("routes"):
            raise ValueError("OSRM could not calculate route: {}".format(route_data.get("message", "unknown error")))

        # Distance is in meters, convert to km
        distance_meters = route_data["routes"][0]["distance"]
        return {
            "distance_km": round(distance_meters / 1000, 2),
            "has_tolls": False,
        }

    except requests.exceptions.RequestException as e:
        logger.error("Routing HTTP error: %s", e)
        raise ValueError("Route calculation failed: {}".format(str(e)))
    except Exception as e:
        logger.error("Routing error: %s", e)
        raise ValueError("Route calculation failed: {}".format(str(e)))


# ─────────────────────────────────────────────────────────────────────────────
# Helper 2 – Pricing  (fully DB-driven)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_price(
    service_type_key: str,
    distance_km:      float,
    has_tolls:        bool,
    vehicle:          str,
    extra_stop:       str | None,
    has_baby_seat:    bool,
    is_return_ride:   bool,
    pickup_time=None,
) -> dict:

    rates                     = _get_rates()
    th_discount, ret_discount = _get_discounts()
    conf                      = _find_rate(rates, vehicle)
    baby_cost                 = 20.00 if has_baby_seat else 0.00

    # ── Load night surcharge rate from Discount model ─────────────────────────
    disc = Discount.objects.first()
    night_surcharge_rate = float(disc.extra_charge_for_down_hours) if disc else 0.30

    # ── Surcharge helpers ─────────────────────────────────────────────────────
    def _night_multiplier() -> float:
        """Returns 1 + surcharge rate if pickup is between midnight and 9am, else 1."""
        if pickup_time is None:
            return 1.0
        try:
            hour = pickup_time.hour if hasattr(pickup_time, "hour") else int(str(pickup_time).split(":")[0])
            if hour < 9:
                return 1.0 + night_surcharge_rate
        except (AttributeError, ValueError):
            pass
        return 1.0

    def _apply_stripe(amount: float) -> float:
        return round(amount * 1.03, 2)

    multiplier = _night_multiplier()

    # ── th: 2 Hour Hire ───────────────────────────────────────────────────────
    if service_type_key == "th":
        base     = conf["th_rate"]
        subtotal = round((base + baby_cost) * multiplier, 2)
        discount = round(subtotal * th_discount, 2)
        total    = _apply_stripe(round(subtotal - discount, 2))

        return {
            "service_type_key":       "th",
            "base":                   base,
            "distance_km":            0,
            "distance_cost":          0,
            "stop_cost":              0,
            "toll_cost":              0,
            "baby_cost":              baby_cost,
            "subtotal_before_return": subtotal,
            "return_multiplier":      False,
            "return_discount":        discount,
            "discount_label":         f"{round(th_discount * 100, 2)}% hire discount",
            "final_price":            total,
            "final_price_cents":      int(total * 100),
        }

    # ── oh: 1 Hour / As Directed ──────────────────────────────────────────────
    if service_type_key == "oh":
        base  = conf["oh_rate"]
        total = _apply_stripe(round((base + baby_cost) * multiplier, 2))

        return {
            "service_type_key":       "oh",
            "base":                   base,
            "distance_km":            0,
            "distance_cost":          0,
            "stop_cost":              0,
            "toll_cost":              0,
            "baby_cost":              baby_cost,
            "subtotal_before_return": total,
            "return_multiplier":      False,
            "return_discount":        0,
            "discount_label":         "",
            "final_price":            total,
            "final_price_cents":      int(total * 100),
        }

    # ── Per-km services (ptp / fair / tair) ───────────────────────────────────
    base          = conf["base_price"]
    distance_cost = round(distance_km * conf["per_km"], 2)
    stop_cost     = conf["stop"] if extra_stop else 0.00
    toll_cost     = 18.50 if has_tolls else 0.00

    subtotal = round(base + distance_cost + stop_cost + toll_cost + baby_cost, 2)

    if is_return_ride:
        return_total    = round(subtotal * 2, 2)
        discount_amount = round(return_total * ret_discount, 2)
        pre_stripe      = round((return_total - discount_amount) * multiplier, 2)
        final_price     = _apply_stripe(pre_stripe)
        discount_label  = f"{round(ret_discount * 100, 2)}% return discount"
    else:
        discount_amount = 0.00
        final_price     = _apply_stripe(round(subtotal * multiplier, 2))
        discount_label  = ""

    return {
        "service_type_key":       service_type_key,
        "base":                   base,
        "distance_km":            distance_km,
        "distance_cost":          distance_cost,
        "stop_cost":              stop_cost,
        "toll_cost":              toll_cost,
        "baby_cost":              baby_cost,
        "subtotal_before_return": subtotal,
        "return_multiplier":      is_return_ride,
        "return_discount":        discount_amount,
        "discount_label":         discount_label,
        "final_price":            final_price,
        "final_price_cents":      int(final_price * 100),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Booking view
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_type(request):
    raw = request.GET.get("type", request.POST.get("service_type_key", "ptp")).lower().strip()
    return raw if raw in SERVICE_TYPES else "ptp"


@login_required
def orders(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    type_key = _resolve_type(request)
    svc      = SERVICE_TYPES[type_key]
    rates    = _get_rates()

    # ── POST ─────────────────────────────────────────────────────────────
    if request.method == "POST":
        action = request.POST.get("action", "calculate")

        pickup      = svc["lock_pickup"]      or request.POST.get("pickup_address", "").strip()
        destination = svc["lock_destination"] or request.POST.get("destination_address", "").strip()
        if type_key in ("th", "oh"):
            destination = f"{svc['label']} — Open Route"

        extra_stop     = request.POST.get("additional_stop", "").strip() or None
        vehicle        = request.POST.get("limo_service_type", rates[0]["name"])
        has_baby_seat  = "baby_seat"   in request.POST
        is_return_ride = "return_ride" in request.POST and type_key not in ("th", "oh")
        flight_number  = request.POST.get("flight_number", "") if svc["show_flight"] else ""
        pickup_time_raw = request.POST.get("pickup_time", "").strip() or None

        form_data = {
            "service_type_key":     type_key,
            "service_type_label":   svc["label"],
            "passenger_name":       request.POST.get("passenger_name", ""),
            "passenger_number":     request.POST.get("passenger_number", ""),
            "passenger_email":      request.POST.get("passenger_email", ""),
            "number_of_passengers": request.POST.get("number_of_passengers", 2),
            "number_of_bags":       request.POST.get("number_of_bags", 2),
            "pickup_address":       pickup,
            "destination_address":  destination,
            "additional_stop":      extra_stop or "",
            "flight_number":        flight_number,
            "pickup_date":          request.POST.get("pickup_date", str(datetime.date.today())),
            "pickup_time":          pickup_time_raw or "",
            "limo_service_type":    vehicle,
            "baby_seat":            has_baby_seat,
            "return_ride":          is_return_ride,
            "special_instruction":  request.POST.get("special_instruction", ""),
            "vehicle_colour":       request.POST.get("vehicle_colour", ""),
            "wedding_ribbon":       request.POST.get("wedding_ribbon", ""),
            "special_signboard":    request.POST.get("special_signboard", ""),
            "show_destination":     svc["show_destination"],
            "show_flight":          svc["show_flight"],
            "lock_pickup":          svc["lock_pickup"],
            "lock_destination":     svc["lock_destination"],
            "is_flat":              svc["flat"],
        }

        def form_error(msg):
            return render(request, "orders/booking_form.html", {
                "error": msg, "form_data": form_data, "svc": svc,
                "type_key": type_key, "rates": rates,
                "google_maps_key": settings.GOOGLE_MAPS_API_KEY,
            })

        # ── Calculate ─────────────────────────────────────────────────────
        if action == "calculate":
            try:
                if type_key in ("th", "oh"):
                    route = {"distance_km": 0, "has_tolls": False}
                else:
                    if not pickup or not destination:
                        return form_error("Please enter both pickup and destination addresses.")
                    route = calculate_distance(pickup, destination, extra_stop)

                breakdown = calculate_price(
                    service_type_key=type_key,
                    distance_km=route["distance_km"],
                    has_tolls=route["has_tolls"],
                    vehicle=vehicle,
                    extra_stop=extra_stop,
                    has_baby_seat=has_baby_seat,
                    is_return_ride=is_return_ride,
                    pickup_time=pickup_time_raw,
                )

                request.session["pending_price"]     = breakdown["final_price"]
                request.session["pending_breakdown"] = breakdown
                request.session["pending_has_tolls"] = route["has_tolls"]

                return render(request, "orders/booking_summary_preview.html", {
                    "form_data":   form_data,
                    "final_price": breakdown["final_price"],
                    "breakdown":   breakdown,
                    "has_tolls":   route["has_tolls"],
                    "svc":         svc,
                    "type_key":    type_key,
                    "rates":       rates,
                })

            except Exception as exc:
                return form_error(f"Route calculation failed: {exc}")

        # ── Confirm → Order → Stripe Checkout ─────────────────────────────
        elif action == "confirm":
            final_price = request.session.get("pending_price")
            if final_price is None:
                return form_error("Your session expired. Please recalculate the price.")

            try:
                order = Order.objects.create(
                    user=request.user,
                    service_type=type_key,
                    passenger_name=form_data["passenger_name"],
                    passenger_number=form_data["passenger_number"],
                    passenger_email=form_data["passenger_email"],
                    number_of_passengers=form_data["number_of_passengers"],
                    number_of_bags=form_data["number_of_bags"],
                    pickup_address=pickup,
                    destination_address=destination,
                    additional_stop=extra_stop,
                    flight_number=flight_number,
                    pickup_date=form_data["pickup_date"],
                    pickup_time=pickup_time_raw or datetime.time(0, 0),
                    limo_service_type=vehicle,
                    baby_seat=has_baby_seat,
                    return_ride=is_return_ride,
                    special_instruction=form_data["special_instruction"],
                    vehicle_colour=form_data["vehicle_colour"],
                    wedding_ribbon=form_data["wedding_ribbon"],
                    special_signboard=form_data["special_signboard"],
                    total_price=final_price,
                    paid=False,
                )
            except Exception as exc:
                return form_error(f"Could not save your booking: {exc}")

            base_status_url = request.build_absolute_uri(reverse("status", args=[order.id]))
            success_url     = base_status_url + "?session_id={CHECKOUT_SESSION_ID}"
            cancel_url      = base_status_url

            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    mode="payment",
                    line_items=[{
                        "price_data": {
                            "currency": "aud",
                            "unit_amount": int(final_price * 100),
                            "product_data": {
                                "name": f"{svc['label']} — Melbourne Chauffeur",
                                "description": (
                                    f"{pickup} → {destination} on {form_data['pickup_date']}"
                                    if type_key not in ("th", "oh")
                                    else f"{svc['label']} from {pickup} on {form_data['pickup_date']}"
                                ),
                            },
                        },
                        "quantity": 1,
                    }],
                    customer_email=form_data["passenger_email"] or None,
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={
                        "order_id":     order.id,
                        "service_type": type_key,
                        "passenger":    form_data["passenger_name"],
                        "pickup":       pickup,
                        "dropoff":      destination,
                        "pickup_date":  form_data["pickup_date"],
                    },
                )
                order.stripe_payment_intent_id = session.id
                order.save(update_fields=["stripe_payment_intent_id"])
                for k in ("pending_price", "pending_breakdown", "pending_has_tolls"):
                    request.session.pop(k, None)
                return HttpResponseRedirect(session.url)

            except stripe.error.StripeError as exc:
                order.delete()
                return form_error(f"Payment setup failed: {exc.user_message}")

    # ── GET ───────────────────────────────────────────────────────────────
    prefill_email = request.user.email or ""
    prefill_phone = ""
    try:
        prefill_phone = request.user.extended_profile.phone or ""
    except AttributeError:
        pass

    form_data = {
        "service_type_key":     type_key,
        "service_type_label":   svc["label"],
        "pickup_address":       svc["lock_pickup"]      or "",
        "destination_address":  svc["lock_destination"] or "",
        "pickup_date":          str(datetime.date.today()),
        "show_destination":     svc["show_destination"],
        "show_flight":          svc["show_flight"],
        "lock_pickup":          svc["lock_pickup"],
        "lock_destination":     svc["lock_destination"],
        "is_flat":              svc["flat"],
        "number_of_passengers": 2,
        "number_of_bags":       2,
        "passenger_email":      prefill_email,
        "passenger_number":     prefill_phone,
        "limo_service_type":    rates[0]["name"],
    }
    return render(request, "orders/booking_form.html", {
        "form_data":       form_data,
        "svc":             svc,
        "type_key":        type_key,
        "rates":           rates,
        "google_maps_key": settings.GOOGLE_MAPS_API_KEY,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Order status
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def order_status(request, order_id):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    order = get_object_or_404(Order, id=order_id, user=request.user)

    session_id = request.GET.get("session_id")
    if session_id and not order.paid:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
                Order.objects.filter(id=order.id, paid=False).update(paid=True)
                order.refresh_from_db()
        except stripe.error.StripeError as exc:
            logger.warning("Could not verify Stripe session %s: %s", session_id, exc)

    template = "orders/booking_confirmed.html" if order.paid else "orders/booking_cancelled.html"
    return render(request, template, {"order": order})


# ─────────────────────────────────────────────────────────────────────────────
# Stripe webhook
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def stripe_webhook(request):
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            request.META.get("HTTP_STRIPE_SIGNATURE", ""),
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        logger.warning("Stripe webhook signature failed: %s", exc)
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session  = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")
        if order_id and session.get("payment_status") == "paid":
            updated = Order.objects.filter(id=order_id, paid=False).update(paid=True)
            if updated:
                logger.info("Order #%s marked paid via webhook.", order_id)

    elif event["type"] == "checkout.session.expired":
        order_id = event["data"]["object"].get("metadata", {}).get("order_id")
        if order_id:
            logger.warning("Checkout session expired for order #%s", order_id)

    return HttpResponse(status=200)
