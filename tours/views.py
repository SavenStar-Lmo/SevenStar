import datetime
import logging
import threading

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import TOUR_TYPE_CHOICES, TourBooking, TourPrice

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Tour catalogue  (static metadata — prices come from TourPrice DB model)
# ─────────────────────────────────────────────────────────────────────────────

TOUR_CATALOGUE = {
    "yarra_valley": {
        "label":    "Yarra Valley Wine Tours",
        "emoji":    "🍷",
        "tagline":  "Sip your way through Victoria's most celebrated wine country.",
        "about":    (
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
    },
    "mornington": {
        "label":    "Mornington Peninsula Wine Tours",
        "emoji":    "🌊",
        "tagline":  "Ocean breezes, rolling vines, and exceptional Pinot — just 90 minutes from Melbourne.",
        "about":    (
            "The Mornington Peninsula is Victoria's most scenic wine destination, stretching "
            "between Port Phillip Bay and Western Port Bay. Celebrated for its maritime-influenced "
            "Pinot Noir and Chardonnay, the region also boasts artisan breweries, farm-gate "
            "producers, and stunning coastal lookouts. Our tours combine the best cellar doors "
            "with unhurried scenic drives along the stunning Mornington coastline."
        ),
        "highlights": [
            "Curated visits to the Peninsula's finest cellar doors.",
            "World-renowned Pinot Noir and Chardonnay tastings.",
            "Scenic coastal and hinterland routes.",
            "Expert local guides who know every hidden gem.",
            "Gourmet lunch stops at award-winning restaurants.",
            "Private and group tour options available.",
        ],
    },
    "great_ocean_road": {
        "label":    "Great Ocean Road Tours",
        "emoji":    "🌊",
        "tagline":  "One of the world's great coastal drives — experienced in complete luxury.",
        "about":    (
            "The Great Ocean Road is one of Australia's most iconic journeys, hugging the "
            "spectacular surf coast and passing through the Otway Ranges before revealing the "
            "breathtaking Twelve Apostles limestone stacks. Our private chauffeur tours let you "
            "travel at your own pace, stopping at every viewpoint, waterfall, and wildlife "
            "encounter without the stress of driving narrow cliff-edge roads yourself."
        ),
        "highlights": [
            "Private chauffeur-driven tours — no bus crowds.",
            "The iconic Twelve Apostles, Loch Ard Gorge, and London Arch.",
            "Otway Rainforest walks and Cape Otway Lighthouse.",
            "Flexible itinerary — stop wherever you choose.",
            "Koala and wildlife spotting en route.",
            "Full-day and sunrise/sunset tour options.",
        ],
    },
    "victorian_winery": {
        "label":    "Victorian Winery Tours",
        "emoji":    "🍇",
        "tagline":  "Explore Victoria's diverse wine regions beyond the usual tourist trail.",
        "about":    (
            "Victoria is Australia's most diverse wine state, with over a dozen distinct wine "
            "regions from the alpine valleys of the northeast to the warm Heathcote plains. "
            "Our Victorian Winery Tours take you off the beaten track to discover boutique "
            "producers making extraordinary wines that rarely leave the cellar door. Each "
            "itinerary is tailored to your tastes and interests."
        ),
        "highlights": [
            "Tailor-made itineraries across multiple Victorian wine regions.",
            "Boutique cellar doors not found on mainstream tours.",
            "Knowledgeable drivers passionate about Victorian wine.",
            "Paired tastings with artisan cheese and charcuterie.",
            "Overnight multi-day regional tour packages available.",
            "Intimate groups and corporate events welcome.",
        ],
    },
    "golf": {
        "label":    "Golf Tours",
        "emoji":    "⛳",
        "tagline":  "Play Victoria's finest courses — we handle the driving, you handle the birdies.",
        "about":    (
            "Victoria is home to some of Australia's most prestigious golf courses, from the "
            "Sandbelt's celebrated links to the spectacular clifftop fairways of the Mornington "
            "Peninsula. Our Golf Tours transport you and your group in style, with ample room for "
            "your clubs, refreshments on board, and a driver who will navigate traffic while you "
            "focus on your game."
        ),
        "highlights": [
            "Door-to-door transfers to Victoria's top golf courses.",
            "Ample luggage and golf bag storage in all vehicles.",
            "Multi-course day packages across the Melbourne Sandbelt.",
            "Corporate golf day coordination and group transport.",
            "Refreshments and music of your choice en route.",
            "Sunrise tee-time pickups — we're always on schedule.",
        ],
    },
    "melbourne_victorian": {
        "label":    "Melbourne and Victorian Tours",
        "emoji":    "🏙️",
        "tagline":  "Discover the soul of Melbourne and Victoria's most extraordinary attractions.",
        "about":    (
            "From Melbourne's world-famous laneways, galleries, and food scene to the wider "
            "wonders of Victoria — the Dandenong Ranges, Phillip Island's penguin parade, "
            "Healesville Sanctuary, and the Goldfields historic towns — our city and regional "
            "tours showcase the very best of what this remarkable part of Australia has to offer. "
            "Perfect for visitors and locals who want to explore in complete comfort."
        ),
        "highlights": [
            "Customised Melbourne city tours and hidden laneway experiences.",
            "Phillip Island penguin parade transfers and tours.",
            "Dandenong Ranges and Healesville Sanctuary day trips.",
            "Goldfields and historic town itineraries.",
            "Flexible half-day, full-day, and multi-day options.",
            "Expert local commentary throughout your journey.",
        ],
    },
    "grampians": {
        "label":    "Grampians Tours",
        "emoji":    "🏔️",
        "tagline":  "Ancient sandstone ranges, Aboriginal rock art, and breathtaking panoramas.",
        "about":    (
            "The Grampians National Park is one of Victoria's most spectacular natural landscapes, "
            "featuring dramatic sandstone mountain ranges, stunning waterfalls, abundant wildlife, "
            "and some of Australia's most significant Aboriginal rock art sites. Located 260 km "
            "west of Melbourne, our Grampians tours let you experience this UNESCO-significant "
            "wilderness in total comfort and safety."
        ),
        "highlights": [
            "Private chauffeur transfers from Melbourne to the Grampians.",
            "MacKenzie Falls, Pinnacle Lookout, and Boroka Lookout.",
            "Aboriginal rock art sites with cultural context.",
            "Wildlife encounters — kangaroos, emus, and koalas.",
            "Grampians wineries and Halls Gap dining.",
            "Overnight and two-day itinerary packages available.",
        ],
    },
    "peninsula_hot_springs": {
        "label":    "Peninsula Hot Springs Tours",
        "emoji":    "♨️",
        "tagline":  "Soak, relax, and rejuvenate — arrive and depart in complete luxury.",
        "about":    (
            "Peninsula Hot Springs is Australia's premier bathing and spa destination, set across "
            "65 acres of natural thermal landscape on the Mornington Peninsula. With over 80 "
            "thermal bathing pools, spa treatments, and wellness experiences, it is the perfect "
            "escape from the city. Our chauffeur service ensures you arrive relaxed and leave "
            "even more refreshed — no parking, no driving after a day of bliss."
        ),
        "highlights": [
            "Return chauffeur transfers from Melbourne to Peninsula Hot Springs.",
            "Flexible departure times to suit your session booking.",
            "Combine with Mornington Peninsula wine tour on the same day.",
            "Comfortable, spacious vehicles perfect post-spa.",
            "Optional scenic coastal route through Frankston and Dromana.",
            "Group bookings and hen's party packages welcome.",
        ],
    },
    "fruit_picking": {
        "label":    "Fruit Picking Tours",
        "emoji":    "🍓",
        "tagline":  "From vine to basket — a fresh, family-friendly Victorian farm experience.",
        "about":    (
            "Victoria's fertile valleys and orchards produce some of Australia's finest stone "
            "fruits, berries, and tree fruits. Our Fruit Picking Tours take families and groups "
            "to working farms and orchards in the Yarra Valley, Mornington Peninsula, and "
            "Wandin regions where you pick your own seasonal produce straight from the vine "
            "or tree. A wonderful, hands-on day out for all ages."
        ),
        "highlights": [
            "Family-friendly farm tours in Victoria's best fruit-growing regions.",
            "Seasonal availability — strawberries, cherries, apples, and berries.",
            "Yarra Valley and Wandin orchard visits.",
            "Combine with winery or distillery stops for adults.",
            "All ages welcome — great for school holidays.",
            "Relaxed, flexible pace with knowledgeable drivers.",
        ],
    },
    "victorian_ski": {
        "label":    "Victorian Ski Tours",
        "emoji":    "⛷️",
        "tagline":  "Hit the slopes stress-free — we handle the alpine roads so you don't have to.",
        "about":    (
            "Victoria's alpine resorts — Mount Buller, Falls Creek, Mount Hotham, and Lake "
            "Mountain — offer spectacular skiing and snowboarding from June to September. "
            "The winding mountain roads can be challenging, especially with ski gear and after "
            "a long day on the slopes. Our Ski Tours provide safe, comfortable, and reliable "
            "transfers to the snowfields so you arrive fresh and ready to ski."
        ),
        "highlights": [
            "Transfers to Mount Buller, Falls Creek, Hotham, and Lake Mountain.",
            "Ample ski bag and equipment storage in every vehicle.",
            "Early morning departures to maximise your time on the snow.",
            "Return transfers — no driving tired alpine roads at night.",
            "Group bookings and family ski trip packages.",
            "Season pass holders and day-trippers equally welcome.",
        ],
    },
}

# Ordered list for the selection page
TOUR_LIST = [
    {"key": k, **v} for k, v in TOUR_CATALOGUE.items()
]


# ─────────────────────────────────────────────────────────────────────────────
# Price helper
# ─────────────────────────────────────────────────────────────────────────────

def _get_tour_price(tour_type_key: str) -> dict:
    """
    Returns price info for a tour type from the DB.
    Falls back to 250.00 if no TourPrice row exists.
    """
    try:
        tp = TourPrice.objects.get(tour_type=tour_type_key)
        raw_price = float(tp.price)
        note = tp.price_note or ""
    except TourPrice.DoesNotExist:
        raw_price = 250.00
        note = ""

    # Add Stripe 3% processing fee
    final_price = round(raw_price * 1.03, 2)

    return {
        "raw_price":        raw_price,
        "final_price":      final_price,
        "final_price_cents": int(final_price * 100),
        "price_note":       note,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Email notifications
# ─────────────────────────────────────────────────────────────────────────────

def _send_tour_notifications_async(booking: TourBooking):
    """
    Fire admin + customer confirmation emails in a background thread.
    """
    def _send():
        reference  = str(booking.id).zfill(6)
        tour_label = dict(TOUR_TYPE_CHOICES).get(booking.tour_type, booking.tour_type)

        BG      = "#111111"
        SURFACE = "#1a1a1a"
        GOLD    = "#b8902e"
        TEXT    = "#e0e0e0"
        MUTED   = "#888888"
        BORDER  = "#2a2a2a"

        def _row(label, value, highlight=False):
            val_style = (
                f"padding:10px 8px;color:{'#ffffff' if highlight else TEXT};"
                f"{'font-size:16px;font-weight:bold;' if highlight else ''}"
            )
            lbl_style = (
                f"padding:10px 8px;color:{GOLD};width:42%;"
                f"{'font-size:16px;font-weight:bold;' if highlight else ''}"
            )
            row_bg = f"background:{SURFACE};" if highlight else ""
            return (
                f"<tr style='border-bottom:1px solid {BORDER};{row_bg}'>"
                f"<td style='{lbl_style}'>{label}</td>"
                f"<td style='{val_style}'>{value}</td>"
                f"</tr>"
            )

        def _table(*rows):
            return (
                f"<table style='width:100%;border-collapse:collapse;font-size:14px;'>"
                + "".join(rows)
                + "</table>"
            )

        # ── ADMIN ─────────────────────────────────────────────────────────
        admin_email = getattr(settings, "ADMIN_EMAIL", None)
        if admin_email:
            rows = [
                _row("Reference",         f"#{reference}"),
                _row("Tour",              tour_label),
                _row("Passenger Name",    booking.passenger_name),
                _row("Passenger Email",   booking.passenger_email),
                _row("Passenger Phone",   booking.passenger_number),
                _row("Pickup Address",    booking.pickup_address),
                _row("Date",              str(booking.booking_date)),
                _row("Time",              str(booking.booking_time)),
                _row("Passengers",        str(booking.number_of_passengers)),
                _row("Bags",              str(booking.number_of_bags)),
            ]
            if booking.special_instruction:
                rows.append(_row("Special Instructions", booking.special_instruction))
            rows.append(_row("Amount Paid", f"A${booking.total_price}", highlight=True))

            html = (
                f"<div style='font-family:Georgia,serif;max-width:600px;margin:auto;"
                f"background:{BG};color:{TEXT};padding:32px;border-radius:8px;'>"
                f"<div style='text-align:center;margin-bottom:24px;'>"
                f"<h1 style='color:{GOLD};font-size:22px;margin:0;'>SevenStar Limo &amp; Chauffeur</h1>"
                f"<p style='color:{MUTED};margin:4px 0 0;'>New Tour Booking Confirmed</p>"
                f"</div>"
                + _table(*rows)
                + f"<p style='text-align:center;color:#555;font-size:12px;margin-top:24px;'>"
                f"SevenStar Limo &amp; Chauffeur Melbourne &middot; Automated Notification</p>"
                f"</div>"
            )
            try:
                send_mail(
                    subject=f"New Tour Booking #{reference} — {booking.passenger_name} ({tour_label})",
                    message=f"New tour booking #{reference} from {booking.passenger_name}. Tour: {tour_label}. Amount: A${booking.total_price}.",
                    from_email=settings.SERVER_EMAIL,
                    recipient_list=[admin_email],
                    html_message=html,
                    fail_silently=True,
                )
            except Exception as exc:
                logger.error("Failed to send admin tour notification for booking #%s: %s", booking.id, exc)

        # ── CUSTOMER ──────────────────────────────────────────────────────
        if booking.passenger_email:
            rows = [
                _row("Reference No.",     f"#{reference}"),
                _row("Tour",              tour_label),
                _row("Name",              booking.passenger_name),
                _row("Pickup Address",    booking.pickup_address),
                _row("Date",              str(booking.booking_date)),
                _row("Time",              str(booking.booking_time)),
                _row("Passengers",        str(booking.number_of_passengers)),
            ]
            if booking.special_instruction:
                rows.append(_row("Special Instructions", booking.special_instruction))
            rows.append(_row("Amount Paid", f"A${booking.total_price}", highlight=True))

            html = (
                f"<div style='font-family:Georgia,serif;max-width:600px;margin:auto;"
                f"background:{BG};color:{TEXT};padding:32px;border-radius:8px;'>"
                f"<div style='text-align:center;margin-bottom:28px;'>"
                f"<h1 style='color:{GOLD};font-size:24px;margin:0;letter-spacing:1px;'>"
                f"SevenStar Limo &amp; Chauffeur</h1>"
                f"<p style='color:{MUTED};margin:6px 0 0;font-size:13px;"
                f"letter-spacing:2px;text-transform:uppercase;'>Tour Booking Confirmed</p>"
                f"</div>"
                f"<p style='color:{TEXT};font-size:15px;margin:0 0 20px;'>"
                f"Dear {booking.passenger_name},<br><br>"
                f"Thank you for choosing SevenStar. Your {tour_label} booking has been confirmed "
                f"and payment received. Please find your booking details below."
                f"</p>"
                + _table(*rows)
                + f"<div style='margin-top:24px;padding:16px;background:{SURFACE};"
                f"border-left:3px solid {GOLD};border-radius:4px;'>"
                f"<p style='margin:0;color:{MUTED};font-size:13px;line-height:1.6;'>"
                f"Please save your reference number "
                f"<strong style='color:{GOLD};'>#{reference}</strong> for any enquiries. "
                f"Our driver will contact you prior to your tour date."
                f"</p></div>"
                f"<p style='text-align:center;color:#555;font-size:12px;margin-top:28px;'>"
                f"SevenStar Limo &amp; Chauffeur Melbourne<br>"
                f"This is an automated confirmation — please do not reply to this email."
                f"</p></div>"
            )
            try:
                send_mail(
                    subject=f"Tour Booking Confirmed — Reference #{reference} ({tour_label})",
                    message=(
                        f"Dear {booking.passenger_name},\n\n"
                        f"Your tour booking has been confirmed.\n"
                        f"Reference: #{reference}\n"
                        f"Tour: {tour_label}\n"
                        f"Pickup: {booking.pickup_address}\n"
                        f"Date: {booking.booking_date}\n"
                        f"Amount Paid: A${booking.total_price}\n\n"
                        f"Thank you for choosing SevenStar Limo & Chauffeur."
                    ),
                    from_email=settings.SERVER_EMAIL,
                    recipient_list=[booking.passenger_email],
                    html_message=html,
                    fail_silently=True,
                )
            except Exception as exc:
                logger.error("Failed to send customer tour confirmation for booking #%s: %s", booking.id, exc)

    threading.Thread(target=_send, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Main booking view
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def tour_booking(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Resolve tour type from ?type= query param
    raw_type = request.GET.get("type", request.POST.get("tour_type", "")).lower().strip()
    valid_keys = {k for k, _ in TOUR_TYPE_CHOICES}

    # No type → show tour selection page
    if not raw_type or raw_type not in valid_keys:
        # Build enriched list with DB prices for display
        tours_with_prices = []
        for item in TOUR_LIST:
            price_info = _get_tour_price(item["key"])
            tours_with_prices.append({**item, **price_info})
        return render(request, "tours/tour_select.html", {
            "tours": tours_with_prices,
        })

    tour_key  = raw_type
    tour_info = TOUR_CATALOGUE[tour_key]
    price_info = _get_tour_price(tour_key)

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
        num_passengers   = request.POST.get("number_of_passengers", 2)
        num_bags         = request.POST.get("number_of_bags", 2)
        instructions     = request.POST.get("special_instruction", "").strip()

        def form_error(msg):
            return render(request, "tours/tour_booking_form.html", {
                "error":       msg,
                "tour_key":    tour_key,
                "tour":        tour_info,
                "price_info":  price_info,
                "form_data": {
                    "passenger_name":      passenger_name,
                    "passenger_number":    passenger_number,
                    "passenger_email":     passenger_email,
                    "pickup_address":      pickup_address,
                    "booking_date":        booking_date_raw,
                    "booking_time":        booking_time_raw,
                    "number_of_passengers": num_passengers,
                    "number_of_bags":      num_bags,
                    "special_instruction": instructions,
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

        try:
            booking_date = datetime.date.fromisoformat(booking_date_raw)
        except ValueError:
            return form_error("Invalid date format.")

        try:
            h, m = booking_time_raw.split(":")
            booking_time = datetime.time(int(h), int(m))
        except (ValueError, AttributeError):
            booking_time = datetime.time(8, 0)

        final_price = price_info["final_price"]

        # Create booking (unpaid until Stripe confirms)
        try:
            booking = TourBooking.objects.create(
                user=request.user,
                tour_type=tour_key,
                passenger_name=passenger_name,
                passenger_number=passenger_number,
                passenger_email=passenger_email,
                number_of_passengers=num_passengers,
                number_of_bags=num_bags,
                pickup_address=pickup_address,
                booking_date=booking_date,
                booking_time=booking_time,
                special_instruction=instructions or None,
                total_price=final_price,
                paid=False,
            )
        except Exception as exc:
            return form_error(f"Could not save your booking: {exc}")

        base_status_url = request.build_absolute_uri(
            reverse("tour_status", args=[booking.id])
        )
        success_url = base_status_url + "?session_id={CHECKOUT_SESSION_ID}"
        cancel_url  = base_status_url

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": "aud",
                        "unit_amount": int(final_price * 100),
                        "product_data": {
                            "name": f"{tour_info['label']} — SevenStar Limo",
                            "description": (
                                f"{passenger_name} · {num_passengers} passenger(s) · "
                                f"{booking_date_raw}"
                            ),
                        },
                    },
                    "quantity": 1,
                }],
                customer_email=passenger_email or None,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "booking_id":  booking.id,
                    "tour_type":   tour_key,
                    "passenger":   passenger_name,
                    "tour_date":   booking_date_raw,
                },
            )
            booking.stripe_payment_intent_id = session.id
            booking.save(update_fields=["stripe_payment_intent_id"])
            return HttpResponseRedirect(session.url)

        except stripe.error.StripeError as exc:
            booking.delete()
            return form_error(f"Payment setup failed: {exc.user_message}")

    # ── GET ───────────────────────────────────────────────────────────────────
    form_data = {
        "passenger_email":      prefill_email,
        "passenger_number":     prefill_phone,
        "booking_date":         str(datetime.date.today()),
        "number_of_passengers": 2,
        "number_of_bags":       2,
    }

    return render(request, "tours/tour_booking_form.html", {
        "tour_key":        tour_key,
        "tour":            tour_info,
        "price_info":      price_info,
        "form_data":       form_data,
        "google_maps_key": settings.GOOGLE_MAPS_API_KEY,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Status view
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def tour_status(request, booking_id):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    booking = get_object_or_404(TourBooking, id=booking_id, user=request.user)

    session_id = request.GET.get("session_id")
    if session_id and not booking.paid:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
                updated = TourBooking.objects.filter(id=booking.id, paid=False).update(paid=True)
                booking.refresh_from_db()
                if updated:
                    _send_tour_notifications_async(booking)
        except stripe.error.StripeError as exc:
            logger.warning("Could not verify Stripe session %s: %s", session_id, exc)

    tour_info = TOUR_CATALOGUE.get(booking.tour_type, {})

    if booking.paid:
        return render(request, "tours/tour_confirmed.html", {
            "booking":   booking,
            "tour_info": tour_info,
        })
    return render(request, "tours/tour_cancelled.html", {
        "booking":   booking,
        "tour_info": tour_info,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Stripe webhook
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def tour_stripe_webhook(request):
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            request.META.get("HTTP_STRIPE_SIGNATURE", ""),
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        logger.warning("Tour Stripe webhook signature failed: %s", exc)
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session    = event["data"]["object"]
        booking_id = session.get("metadata", {}).get("booking_id")
        if booking_id and session.get("payment_status") == "paid":
            updated = TourBooking.objects.filter(id=booking_id, paid=False).update(paid=True)
            if updated:
                logger.info("TourBooking #%s marked paid via webhook.", booking_id)
                booking_obj = TourBooking.objects.filter(id=booking_id).first()
                if booking_obj:
                    _send_tour_notifications_async(booking_obj)

    elif event["type"] == "checkout.session.expired":
        booking_id = event["data"]["object"].get("metadata", {}).get("booking_id")
        if booking_id:
            logger.warning("Tour checkout session expired for booking #%s", booking_id)

    return HttpResponse(status=200)
