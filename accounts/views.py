import random
import time

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings

from .models import ExtendedProfile


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _generate_otp():
    return str(random.randint(100000, 999999))


def _send_otp_email(email, otp, first_name):
    subject = "Your Melbourne Chauffeur verification code"
    message = (
        f"Hi {first_name},\n\n"
        f"Your 6-digit verification code is:\n\n"
        f"  {otp}\n\n"
        f"This code expires in 10 minutes.\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"— Melbourne Chauffeur & Limo Service"
    )
    html_message = f"""
    <div style="font-family:'Jost',Arial,sans-serif;max-width:520px;margin:0 auto;background:#faf8f3;border:1px solid #e8e2d6;border-radius:12px;overflow:hidden;">
        <div style="background:#1a1714;padding:28px 32px;border-bottom:2px solid #b8902e;">
            <p style="margin:0;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#d4aa4a;font-weight:600;">SevenStar Limo</p>
        </div>
        <div style="padding:36px 32px;">
            <p style="margin:0 0 8px;font-size:13px;color:#6b6560;">Hi {first_name},</p>
            <p style="margin:0 0 28px;font-size:13px;color:#6b6560;line-height:1.7;">
                Use the code below to verify your email address and complete your account registration.
            </p>
            <div style="background:#fff;border:1px solid #e8e2d6;border-radius:10px;padding:24px;text-align:center;margin-bottom:28px;">
                <p style="margin:0 0 6px;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#a09890;">Verification Code</p>
                <p style="margin:0;font-size:38px;font-weight:600;letter-spacing:10px;color:#1a1714;font-family:monospace;">{otp}</p>
            </div>
            <p style="margin:0;font-size:12px;color:#a09890;line-height:1.6;">
                This code expires in <strong>10 minutes</strong>.<br>
                If you didn't create an account, you can safely ignore this email.
            </p>
        </div>
        <div style="padding:16px 32px;border-top:1px solid #e8e2d6;background:#f3efe6;">
            <p style="margin:0;font-size:11px;color:#a09890;">&copy; SevenStar  Chauffeur &amp; Limo Service</p>
        </div>
    </div>
    """
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        html_message=html_message,
        fail_silently=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Auth views
# ─────────────────────────────────────────────────────────────────────────────

def user_login(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        password   = request.POST.get('password', '')
        next_url   = request.POST.get('next', '')

        if not identifier or not password:
            messages.error(request, 'Please enter your email or phone and password.')
            return render(request, 'accounts/login.html', {'identifier': identifier, 'next': next_url})

        username = None

        if '@' in identifier:
            try:
                user = User.objects.get(email__iexact=identifier)
                username = user.username
            except User.DoesNotExist:
                username = None
        else:
            try:
                profile  = ExtendedProfile.objects.get(phone=identifier)
                username = profile.user.username
            except ExtendedProfile.DoesNotExist:
                username = None

        user = authenticate(request, username=username, password=password) if username else None

        if user is not None:
            login(request, user)
            return redirect(next_url or 'home')
        else:
            messages.error(request, 'No account found with those details. Please check and try again.')
            return render(request, 'accounts/login.html', {'identifier': identifier, 'next': next_url})

    return render(request, 'accounts/login.html', {'next': request.GET.get('next', '')})


def signup(request):
    """Step 1 — collect details, validate, send OTP, redirect to verify."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip().lower()
        phone      = request.POST.get('phone', '').strip()
        password1  = request.POST.get('password1', '')
        password2  = request.POST.get('password2', '')

        # ── Preserve form data for re-render on error
        form_data = {
            'first_name': first_name,
            'last_name':  last_name,
            'email':      email,
            'phone':      phone,
        }

        # ── Validation ──────────────────────────────────────
        if not all([first_name, last_name, email, phone, password1, password2]):
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/signup.html', {'form': form_data})

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'accounts/signup.html', {'form': form_data})

        if len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, 'accounts/signup.html', {'form': form_data})

        # ── Duplicate checks ─────────────────────────────────
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'An account with this email address already exists.')
            return render(request, 'accounts/signup.html', {'form': form_data})

        if ExtendedProfile.objects.filter(phone=phone).exists():
            messages.error(request, 'An account with this phone number already exists.')
            return render(request, 'accounts/signup.html', {'form': form_data})

        # ── Generate OTP and stash pending registration in session ───────────
        otp = _generate_otp()

        request.session['pending_signup'] = {
            'first_name': first_name,
            'last_name':  last_name,
            'email':      email,
            'phone':      phone,
            'password':   password1,      # plain-text only in session (short-lived)
            'otp':        otp,
            'otp_ts':     time.time(),    # unix timestamp for expiry check
            'attempts':   0,
        }

        # ── Send email ───────────────────────────────────────
        try:
            _send_otp_email(email, otp, first_name)
        except Exception as e:
            print(f"[signup] email send failed: {e}")
            messages.error(request, 'We couldn\'t send a verification email. Please try again.')
            return render(request, 'accounts/signup.html', {'form': form_data})

        return redirect('verify_email')

    return render(request, 'accounts/signup.html')


def verify_email(request):
    """Step 2 — user enters the 6-digit OTP; account is created on success."""
    if request.user.is_authenticated:
        return redirect('home')

    pending = request.session.get('pending_signup')
    if not pending:
        messages.error(request, 'Your session has expired. Please fill in the form again.')
        return redirect('signup')

    OTP_EXPIRY_SECONDS = 600   # 10 minutes
    MAX_ATTEMPTS       = 5

    if request.method == 'POST':
        action = request.POST.get('action', 'verify')

        # ── Resend OTP ──────────────────────────────────────
        if action == 'resend':
            new_otp = _generate_otp()
            pending['otp']      = new_otp
            pending['otp_ts']   = time.time()
            pending['attempts'] = 0
            request.session['pending_signup'] = pending
            request.session.modified = True

            try:
                _send_otp_email(pending['email'], new_otp, pending['first_name'])
                messages.success(request, 'A new code has been sent to your email.')
            except Exception as e:
                print(f"[verify_email] resend failed: {e}")
                messages.error(request, 'Failed to resend code. Please try again.')

            return redirect('verify_email')

        # ── Verify OTP ──────────────────────────────────────
        entered = request.POST.get('otp', '').strip().replace(' ', '')

        # Check expiry
        age = time.time() - pending.get('otp_ts', 0)
        if age > OTP_EXPIRY_SECONDS:
            del request.session['pending_signup']
            messages.error(request, 'Your code has expired. Please sign up again.')
            return redirect('signup')

        # Check attempts
        pending['attempts'] = pending.get('attempts', 0) + 1
        request.session['pending_signup'] = pending
        request.session.modified = True

        if pending['attempts'] > MAX_ATTEMPTS:
            del request.session['pending_signup']
            messages.error(request, 'Too many incorrect attempts. Please sign up again.')
            return redirect('signup')

        if entered != pending['otp']:
            remaining = MAX_ATTEMPTS - pending['attempts']
            messages.error(
                request,
                f'Incorrect code. {remaining} attempt{"s" if remaining != 1 else ""} remaining.'
            )
            return render(request, 'accounts/verify_email.html', {
                'email': pending['email'],
                'first_name': pending['first_name'],
            })

        # ── OTP correct — create user ────────────────────────
        try:
            # Re-check uniqueness (race condition safety)
            if User.objects.filter(email__iexact=pending['email']).exists():
                del request.session['pending_signup']
                messages.error(request, 'An account with this email already exists.')
                return redirect('signup')

            user = User.objects.create_user(
                username   = pending['email'],
                email      = pending['email'],
                password   = pending['password'],
                first_name = pending['first_name'],
                last_name  = pending['last_name'],
            )
            ExtendedProfile.objects.create(user=user, phone=pending['phone'])

            del request.session['pending_signup']

            login(request, user)
            messages.success(request, f'Welcome, {user.first_name}! Your account has been created.')
            return redirect('home')

        except Exception as e:
            print(f"[verify_email] create_user failed: {e}")
            messages.error(request, 'Something went wrong. Please try again.')
            return redirect('signup')

    # GET
    return render(request, 'accounts/verify_email.html', {
        'email':      pending['email'],
        'first_name': pending['first_name'],
    })


# ─────────────────────────────────────────────────────────────────────────────
#  Profile views  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def profile(request):
    return render(request, 'accounts/profile.html')


@login_required
def profile_update_details(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip().lower()
        phone      = request.POST.get('phone', '').strip()

        if not all([first_name, last_name, email, phone]):
            messages.error(request, 'All fields are required.')
            return redirect('profile')

        if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
            messages.error(request, 'That email address is already in use.')
            return redirect('profile')

        if ExtendedProfile.objects.filter(phone=phone).exclude(user=request.user).exists():
            messages.error(request, 'That phone number is already in use.')
            return redirect('profile')

        request.user.first_name = first_name
        request.user.last_name  = last_name
        request.user.email      = email
        request.user.username   = email
        request.user.save()

        request.user.extended_profile.phone = phone
        request.user.extended_profile.save()

        messages.success(request, 'Your details have been updated.')
    return redirect('profile')


@login_required
def profile_update_password(request):
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new_pw  = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')

        if not request.user.check_password(current):
            messages.error(request, 'Your current password is incorrect.')
            return redirect('profile')

        if len(new_pw) < 8:
            messages.error(request, 'New password must be at least 8 characters.')
            return redirect('profile')

        if new_pw != confirm:
            messages.error(request, 'New passwords do not match.')
            return redirect('profile')

        request.user.set_password(new_pw)
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, 'Password updated successfully.')
    return redirect('profile')


@login_required
def profile_delete(request):
    if request.method == 'POST':
        request.user.delete()
        messages.success(request, 'Your account has been deleted.')
        return redirect('home')
    return redirect('profile')
