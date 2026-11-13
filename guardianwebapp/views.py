from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from requests import request
from .models import Profile
import random
import time
import re
from twilio.rest import Client
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import (
    LiveWatchSession, GPSPoint, Checkpoint,
    DangerEvent, GuardianWatchLink, SessionStatus,
)
from .forms import StartSessionForm, CheckpointFormSet
from .serializers import (
    session_summary, gps_point_to_dict,
    checkpoint_to_dict, danger_event_to_dict,
)
from django.http import JsonResponse
from .models import EmergencyAlert

def welcome(request):
    return render(request, 'guardianwebapp/welcome_page.html')


@csrf_exempt
def registration_view(request):

    if request.method == "POST":

        username = request.POST.get('username')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        role = request.POST.get('role')

        if not username or not phone or not password or not role:
            messages.error(request, "All fields are required")
            return redirect('registration_view')

        if not re.fullmatch(r'\d{10}', phone):
            messages.error(request, "Phone number must be exactly 10 digits")
            return redirect('registration_view')

        password_pattern = r'^(?=.*[A-Z])(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,12}$'

        if not re.match(password_pattern, password):
            messages.error(
                request,
                "Password must be 8-12 characters with one uppercase and one special character"
            )
            return redirect('registration_view')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('registration_view')

        otp = str(random.randint(100000, 999999))
        client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
        )
        try:
            message = client.messages.create(
            body=f"Your GuardianWeb OTP is {otp}",
            from_=settings.TWILIO_PHONE_NUMBER,
            to="+91" + phone)
            print("Message SID:", message.sid)

        except Exception as e:
            print("Twilio Error:", e)

        request.session['temp_user'] = {
            'username': username,
            'phone': phone,
            'password': password,
            'role': role,
            'otp': otp,
            'otp_time': time.time()
        }

        # Replace with SMS API later
        print(f"OTP for {phone}: {otp}")

        return redirect('verify_otp')

    return render(
        request,
        'guardianwebapp/registration_page.html'
    )


@csrf_exempt
def verify_otp(request):

    data = request.session.get('temp_user')

    if not data:
        messages.error(
            request,
            "Session expired. Please register again."
        )
        return redirect('registration_view')

    if request.method == "POST":

        if 'resend' in request.POST:

            otp = str(random.randint(100000, 999999))

            data['otp'] = otp
            data['otp_time'] = time.time()

            request.session['temp_user'] = data

            print(f"New OTP for {data['phone']} : {otp}")

            messages.success(
                request,
                "OTP resent successfully."
            )

            return redirect('verify_otp')

        current_time = time.time()

        if current_time - data['otp_time'] > 60:

            messages.error(
                request,
                "OTP expired. Please resend OTP."
            )

            return render(
                request,
                'guardianwebapp/verify_otp.html'
            )

        entered_otp = request.POST.get('otp')

        if entered_otp == data['otp']:

            user = User.objects.create_user(
                username=data['username'],
                password=data['password']
            )

            Profile.objects.create(
                user=user,
                phone=data['phone'],
                role=data['role']
            )

            request.session.flush()

            messages.success(
                request,
                "Registration Successful"
            )

            return redirect('login_page')

        else:

            messages.error(
                request,
                "Invalid OTP"
            )

    return render(
        request,
        'guardianwebapp/verify_otp.html'
    )
@csrf_exempt
def login_view(request):

    if request.method == "POST":

        phone = request.POST.get("phone")
        password = request.POST.get("password")

        # Form Validation
        if not phone:
            messages.error(request, "Phone number is required")
            return render(request, "guardianwebapp/login_page.html")

        # Original validation:
        # if len(phone) != 10:
        #     messages.error(request, "Enter a valid 10-digit phone number")
        #     return render(request, "guardianwebapp/login_page.html")
        if not phone or not phone.isdigit() or len(phone) != 10:
            messages.error(request, "Enter a valid 10-digit phone number")
            return render(request, "guardianwebapp/login_page.html")

        if not password:
            messages.error(request, "Password is required")
            return render(request, "guardianwebapp/login_page.html")

        try:
            profile = Profile.objects.get(phone=phone)

            user = authenticate(
                request,
                username=profile.user.username,
                password=password
            )

            if user is not None:

                login(request, user)

                if user.is_superuser:
                    return redirect("admin_dashboard")

                if profile.role == "user":
                    return redirect("user_dashboard")

                elif profile.role == "guardian":
                    return redirect("guardian_dashboard")

                elif profile.role == "volunteer":
                    return redirect("volunteer_dashboard")

            else:
                messages.error(request, "Invalid password")

        except Profile.DoesNotExist:
            messages.error(request, "Phone number not registered")

    return render(request, "guardianwebapp/login_page.html")


def logout_view(request):

    logout(request)

    return redirect('login_page')

@csrf_exempt
def forgot_password(request):

    if request.method == "POST":

        phone = request.POST.get('phone')

        if not re.fullmatch(r'\d{10}', phone):
            messages.error(request, "Phone number must be exactly 10 digits")
            return redirect('forgot_password')

        profile = Profile.objects.filter(phone=phone).first()

        if not profile:
            messages.error(request, "No account found with that phone number")
            return redirect('forgot_password')

        otp = str(random.randint(100000, 999999))
        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        try:
            message = client.messages.create(
                body=f"Your GuardianWeb password reset OTP is {otp}",
                from_=settings.TWILIO_PHONE_NUMBER,
                to="+91" + phone)
            print("Message SID:", message.sid)

        except Exception as e:
            print("Twilio Error:", e)

        request.session['temp_reset'] = {
            'user_id': profile.user.id,
            'phone': phone,
            'otp': otp,
            'otp_time': time.time()
        }

        print(f"Reset OTP for {phone}: {otp}")

        return redirect('verify_reset_otp')

    return render(
        request,
        'guardianwebapp/forgot_password.html'
    )


@csrf_exempt
def verify_reset_otp(request):

    data = request.session.get('temp_reset')

    if not data:
        messages.error(
            request,
            "Session expired. Please try again."
        )
        return redirect('forgot_password')

    if request.method == "POST":

        if 'resend' in request.POST:

            otp = str(random.randint(100000, 999999))

            data['otp'] = otp
            data['otp_time'] = time.time()

            request.session['temp_reset'] = data

            print(f"New reset OTP for {data['phone']} : {otp}")

            messages.success(
                request,
                "OTP resent successfully."
            )

            return redirect('verify_reset_otp')

        current_time = time.time()

        if current_time - data['otp_time'] > 60:

            messages.error(
                request,
                "OTP expired. Please resend OTP."
            )

            return render(
                request,
                'guardianwebapp/verify_reset_otp.html'
            )

        entered_otp = request.POST.get('otp')

        if entered_otp == data['otp']:

            request.session['otp_verified_reset'] = True

            return redirect('reset_password')

        else:

            messages.error(
                request,
                "Invalid OTP"
            )

    return render(
        request,
        'guardianwebapp/verify_reset_otp.html'
    )


@csrf_exempt
def reset_password(request):

    data = request.session.get('temp_reset')

    if not data or not request.session.get('otp_verified_reset'):
        messages.error(request, "Please verify OTP first.")
        return redirect('forgot_password')

    if request.method == "POST":

        new_password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        password_pattern = r'^(?=.*[A-Z])(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,12}$'

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('reset_password')

        if not re.match(password_pattern, new_password):
            messages.error(
                request,
                "Password must be 8-12 characters with one uppercase and one special character"
            )
            return redirect('reset_password')

        user = User.objects.get(id=data['user_id'])
        user.set_password(new_password)
        user.save()

        request.session.flush()

        messages.success(request, "Password reset successful. Please log in.")
        return redirect('login_page')

    return render(
        request,
        'guardianwebapp/reset_password.html'
    )

from .models import GuardianWatchLink, LiveWatchSession
from .models import Volunteer
import datetime
from django.db.models import Q
from .models import EmergencyAlert, DangerEvent, Profile

def user_dashboard(request):
    available_volunteers_count = Volunteer.objects.filter(is_available=True).count()
    # Fetch active session first, or fall back to most recent session
    active_session = LiveWatchSession.objects.filter(user=request.user, status=SessionStatus.ACTIVE).first()
    session = active_session if active_session else LiveWatchSession.objects.filter(user=request.user).order_by('-started_at').first()

    # Retrieve all guardians for the session
    guardians = GuardianWatchLink.objects.filter(user=request.user)

    # Best-effort online check for guardians
    # Registered user guardians are online if logged in in the last 60 minutes
    # Viewer links are online if joined in the last 30 minutes
    now = timezone.now()
    for g in guardians:
        g.is_online = False
        if g.guardian:
            if g.guardian.last_login and (now - g.guardian.last_login).total_seconds() < 3600:
                g.is_online = True
        else:
            if (now - g.joined_at).total_seconds() < 1800:
                g.is_online = True

    guardians_count = guardians.count()
    guardians_online_count = sum(1 for g in guardians if getattr(g, 'is_online', False))

    # Location sharing details
    sharing_active = active_session is not None
    
    # Alerts sent this week (last 7 days)
    one_week_ago = now - datetime.timedelta(days=7)
    alerts_sent_week = EmergencyAlert.objects.filter(user=request.user, created_at__gte=one_week_ago).count()

    # Total companion/journey sessions
    total_sessions = LiveWatchSession.objects.filter(user=request.user).count()

    # Fetch activities
    activities = []
    
    # 1. Fetch user's sessions
    user_sessions = LiveWatchSession.objects.filter(user=request.user).order_by('-started_at')[:10]
    for s in user_sessions:
        activities.append({
            'type': 'session_started',
            'title': f"Location sharing started: {s.title}",
            'time': s.started_at,
            'icon': 'ti-map-pin',
            'color': '#EAF3DE',
            'text_color': '#3B6D11'
        })
        if s.ended_at:
            activities.append({
                'type': 'session_ended',
                'title': f"Journey completed ({s.get_status_display()})",
                'time': s.ended_at,
                'icon': 'ti-heart',
                'color': '#EEEDFE',
                'text_color': '#534AB7'
            })
        
        # 2. Danger events for this session
        dangers = s.danger_events.all()
        for d in dangers:
            activities.append({
                'type': 'danger',
                'title': f"{d.get_trigger_display()} alert: {d.description}",
                'time': d.created_at,
                'icon': 'ti-alert-triangle',
                'color': '#FAECE7',
                'text_color': '#993C1D'
            })

    # 3. Emergency alerts for this user
    alerts = EmergencyAlert.objects.filter(user=request.user).order_by('-created_at')[:10]
    for a in alerts:
        activities.append({
            'type': 'sos',
            'title': f"Emergency SOS alert sent ({a.status})",
            'time': a.created_at,
            'icon': 'ti-alert-triangle',
            'color': '#FAECE7',
            'text_color': '#993C1D'
        })

    # Sort activities by time descending and take top 5
    activities.sort(key=lambda x: x['time'], reverse=True)
    recent_activities = activities[:5]

    return render(
        request,
        'guardianwebapp/user_dashboard.html',
        {
            'user': request.user,
            'session': session,
            'guardians': guardians,
            'guardians_count': guardians_count,
            'guardians_online_count': guardians_online_count,
            'sharing_active': sharing_active,
            'alerts_sent_week': alerts_sent_week,
            'total_sessions': total_sessions,
            'recent_activities': recent_activities,
            'available_volunteers_count': available_volunteers_count,
            'sos_history': alerts, 
        }
    )
@login_required
def notifications_view(request):
    now = timezone.now()
    one_month_ago = now - datetime.timedelta(days=30)

    notifications = []

    alerts = EmergencyAlert.objects.filter(user=request.user, created_at__gte=one_month_ago).order_by('-created_at')
    for a in alerts:
        notifications.append({
            'title': f"You triggered an SOS alert ({a.status})",
            'time': a.created_at,
            'icon': 'ti-alert-triangle',
            'color': '#FAECE7',
            'text_color': '#993C1D',
        })

    sessions = LiveWatchSession.objects.filter(user=request.user, started_at__gte=one_month_ago).order_by('-started_at')
    for s in sessions:
        notifications.append({
            'title': f"Location sharing started: {s.title}",
            'time': s.started_at,
            'icon': 'ti-map-pin',
            'color': '#EAF3DE',
            'text_color': '#3B6D11',
        })
        if s.ended_at:
            notifications.append({
                'title': f"Journey completed ({s.get_status_display()})",
                'time': s.ended_at,
                'icon': 'ti-heart',
                'color': '#EEEDFE',
                'text_color': '#534AB7',
            })

    notifications.sort(key=lambda x: x['time'], reverse=True)

    return render(request, "guardianwebapp/notifications.html", {
        "notifications": notifications,
    })

from .models import GuardianWatchLink
@login_required
def guardian_dashboard(request):

    # All sessions this guardian is actually linked to watch
    watch_links = GuardianWatchLink.objects.filter(
        guardian=request.user
    ).select_related('session', 'session__user').order_by('-session__started_at')

    watched_sessions = []
    for link in watch_links:
        session = link.session
        latest_location = session.gps_points.order_by("-recorded_at").first() if hasattr(session, 'gps_points') else None
        watched_sessions.append({
            "session": session,
            "user": session.user,
            "is_active": session.status == SessionStatus.ACTIVE,
            "in_danger": session.status == SessionStatus.DANGER,
            "location": latest_location,
        })

    return render(
        request,
        "guardianwebapp/guardian_dashboard.html",
        {
            "watched_sessions": watched_sessions,
        }
    )

from django.contrib.auth.hashers import check_password
@login_required
def profile_settings(request):
    from .models import Profile

    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        user = request.user

        new_username = request.POST.get("username", "").strip()
        new_phone = request.POST.get("phone", "").strip()
        new_address = request.POST.get("address", "").strip()
        old_password = request.POST.get("old_password", "").strip()
        new_password = request.POST.get("new_password", "").strip()
        profile_picture = request.FILES.get("profile_picture")

        # --- Username ---
        if new_username and new_username != user.username:
            if User.objects.filter(username__iexact=new_username).exclude(id=user.id).exists():
                messages.error(request, "That username is already taken.")
                return redirect("profile_settings")
            user.username = new_username

        # --- Phone: digits only, exactly 10 ---
        if new_phone:
            if not re.fullmatch(r'\d{10}', new_phone):
                messages.error(request, "Phone number must be exactly 10 digits, no letters or symbols.")
                return redirect("profile_settings")
            profile.phone = new_phone

        # --- Address ---
        if new_address:
            profile.address = new_address

        # --- Profile picture ---
        if profile_picture:
            profile.profile_picture = profile_picture

        remove_picture = request.POST.get("remove_picture") == "1"

# --- Profile picture ---
        if remove_picture and profile.profile_picture:
            profile.profile_picture.delete(save=False)  # deletes file from disk
            profile.profile_picture = None
        elif profile_picture:
            profile.profile_picture = profile_picture

        # --- Password change (requires old password + complexity) ---
        if new_password:
            if not old_password:
                messages.error(request, "Enter your current password to set a new one.")
                return redirect("profile_settings")

            if not check_password(old_password, user.password):
                messages.error(request, "Current password is incorrect.")
                return redirect("profile_settings")

            # 8-12 chars, at least 1 uppercase, 1 digit, 1 special char
            pattern = r'^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};:\'",.<>/?]).{8,12}$'
            if not re.fullmatch(pattern, new_password):
                messages.error(
                    request,
                    "Password must be 8–12 characters, with at least 1 uppercase letter, "
                    "1 digit, and 1 special character."
                )
                return redirect("profile_settings")

            user.set_password(new_password)

        user.save()
        profile.save()

        if new_password:
            update_session_auth_hash(request, user)  # keeps user logged in

        messages.success(request, "Profile updated successfully.")
        return redirect("profile_settings")

    return render(request, "guardianwebapp/profile_settings.html", {
        "user": request.user,
        "profile": profile,
    })


@csrf_exempt
def update_location(request):

    if request.method == "POST":

        data = json.loads(request.body)

        session = LiveWatchSession.objects.filter(
            user=request.user,
            status=SessionStatus.ACTIVE
        ).last()

        if session:

            GPSPoint.objects.create(
                session=session,
                latitude=data["latitude"],
                longitude=data["longitude"]
            )

        return JsonResponse({"success": True})

def get_live_location(request):
    from .models import EmergencyAlert

    alert_id = request.GET.get("alert_id")

    if alert_id:
        # Volunteer/guardian tracking a specific person's SOS
        alert = EmergencyAlert.objects.filter(id=alert_id).select_related('session').first()
        if not alert:
            return JsonResponse({"success": False})

        session = alert.session
        if session:
            point = session.gps_points.order_by("-recorded_at").first()
            if point:
                return JsonResponse({
                    "success": True,
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "time": point.recorded_at.strftime("%H:%M:%S")
                })

        # No session/GPS points yet — fall back to the alert's own last known lat/lng
        return JsonResponse({
            "success": True,
            "latitude": alert.latitude,
            "longitude": alert.longitude,
            "time": alert.created_at.strftime("%H:%M:%S")
        })

    else:
        # User dashboard's own live map — their own active session only
        if not request.user.is_authenticated:
            return JsonResponse({"success": False})

        session = LiveWatchSession.objects.filter(
            user=request.user, status=SessionStatus.ACTIVE
        ).order_by("-started_at").first()

        if not session:
            return JsonResponse({"success": False})

        point = session.gps_points.order_by("-recorded_at").first()
        if not point:
            return JsonResponse({"success": False})

        return JsonResponse({
            "success": True,
            "latitude": point.latitude,
            "longitude": point.longitude,
            "time": point.recorded_at.strftime("%H:%M:%S")
        })
def view_location(request):

    session = LiveWatchSession.objects.filter(
        status=SessionStatus.ACTIVE
    ).order_by("-started_at").first()

    location = None

    if session:
        location = session.gps_points.order_by("-recorded_at").first()

    return render(
        request,
        "guardianwebapp/view_location.html",
        {
            "session": session,
            "location": location,
        }
    )

from django.utils import timezone

@login_required
def stop_sharing(request, session_id):
    session = get_object_or_404(LiveWatchSession, id=session_id, user=request.user)

    if session.status in [SessionStatus.ACTIVE, SessionStatus.DANGER, SessionStatus.PAUSED]:
        session.status = SessionStatus.SAFE
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at"])
        messages.success(request, "Location sharing has been stopped. You're marked as safe.")
    else:
        messages.info(request, "This session is already inactive.")

    return redirect("user_dashboard")


from .models import CompanionRequest
from .models import Volunteer
def volunteer_dashboard(request):
    if not hasattr(request.user, 'volunteer'):
        messages.error(request, "You are not registered as a volunteer. Please sign up as a volunteer to access this page.")
        return redirect("user_dashboard")

    volunteer = request.user.volunteer

    return render(request, "guardianwebapp/volunteer_dashboard.html", {
        "volunteer": volunteer,
    })

@login_required
def volunteer_pending_requests(request):
    from .models import EmergencyAlert

    if not hasattr(request.user, 'volunteer'):
        messages.error(request, "You are not registered as a volunteer.")
        return redirect("user_dashboard")

    volunteer = request.user.volunteer

    pending_requests = EmergencyAlert.objects.filter(
        status="Sent"
    ).select_related('user').prefetch_related(
        'session__guardian_links', 'volunteers_notified__user'
    ).order_by('-created_at')

    return render(request, "guardianwebapp/volunteer_pending_requests.html", {
        "requests": pending_requests,
        "volunteer": volunteer,
    })

def volunteer_accepted_requests(request):
    from .models import EmergencyAlert

    if not hasattr(request.user, 'volunteer'):
        messages.error(request, "You are not registered as a volunteer.")
        return redirect("user_dashboard")

    volunteer = request.user.volunteer

    accepted_requests = EmergencyAlert.objects.filter(
        status="Accepted",
        accepted_by=volunteer
    ).select_related('user', 'accepted_by__user').order_by('-created_at')

    return render(request, "guardianwebapp/volunteer_accepted_requests.html", {
        "accepted_requests": accepted_requests,
        "volunteer": volunteer,
    })


def volunteer_nearby_alerts(request):
    from .utils import get_nearby_emergency_alerts

    if not hasattr(request.user, 'volunteer'):
        messages.error(request, "You are not registered as a volunteer.")
        return redirect("user_dashboard")

    volunteer = request.user.volunteer

    nearby_alerts = []
    if volunteer.latitude is not None and volunteer.longitude is not None:
        nearby_alerts = get_nearby_emergency_alerts(
            volunteer.latitude, volunteer.longitude, radius_km=2
        )

    return render(request, "guardianwebapp/volunteer_nearby_alerts.html", {
        "nearby_alerts": nearby_alerts,
        "volunteer": volunteer,
    })


def volunteer_companion_sessions(request):
    from .models import CompanionRequest
    from django.utils import timezone
    from datetime import timedelta

    if not hasattr(request.user, 'volunteer'):
        messages.error(request, "You are not registered as a volunteer.")
        return redirect("user_dashboard")

    volunteer = request.user.volunteer

    # Auto-expire pending requests older than 60 seconds
    cutoff = timezone.now() - timedelta(seconds=60)
    CompanionRequest.objects.filter(
        status="Pending",
        requested_at__lt=cutoff
    ).update(status="AI_Mode")

    # Current: broadcast pending requests, still within the 1-min window
    pending_requests = CompanionRequest.objects.filter(
        status="Pending"
    ).order_by("-requested_at")

    # My active sessions: this volunteer accepted, session still open
    active_requests = CompanionRequest.objects.filter(
        volunteer=volunteer,
        status="Accepted"
    ).order_by("-accepted_at")

    # History: expired (never joined) or completed — global, since unassigned ones
    # were never tied to a specific volunteer
    history_requests = CompanionRequest.objects.filter(
        status__in=["AI_Mode", "Completed", "Rejected"]
    ).order_by("-requested_at")[:20]

    return render(request, "guardianwebapp/volunteer_companion_sessions.html", {
        "pending_requests": pending_requests,
        "active_requests": active_requests,
        "history_requests": history_requests,
        "volunteer": volunteer,
    })

def accept_nearby_alert(request, alert_id):
    from .models import EmergencyAlert

    alert = get_object_or_404(EmergencyAlert, id=alert_id)
    volunteer = request.user.volunteer

    alert.volunteers_notified.add(volunteer)
    alert.status = "Accepted"
    alert.save(update_fields=["status"])

    messages.success(request, f"You've accepted the alert from {alert.user.username}.")
    return redirect("volunteer_dashboard")

def join_companion_session(request, request_id):
    from django.utils import timezone

    volunteer = request.user.volunteer

    # Block if this volunteer already has an active (unfinished) session
    existing_active = CompanionRequest.objects.filter(
        volunteer=volunteer,
        status="Accepted"
    ).exists()

    if existing_active:
        messages.error(request, "You already have an active session. Please end it before joining another.")
        return redirect("volunteer_companion_sessions")

    companion_request = get_object_or_404(CompanionRequest, id=request_id)

    if companion_request.status != "Pending":
        messages.error(request, "This request has already been taken or expired.")
        return redirect("volunteer_companion_sessions")

    companion_request.volunteer = volunteer
    companion_request.status = "Accepted"
    companion_request.accepted_at = timezone.now()
    companion_request.save(update_fields=["volunteer", "status", "accepted_at"])

    messages.success(request, f"You joined {companion_request.user.username}'s session.")
    return redirect("companion_chat", request_id=companion_request.id)

@login_required
def end_companion_session(request, request_id):
    companion_request = get_object_or_404(CompanionRequest, id=request_id)

    is_requester = companion_request.user == request.user
    is_assigned_volunteer = (
        hasattr(request.user, 'volunteer') and
        companion_request.volunteer == request.user.volunteer
    )

    if not (is_requester or is_assigned_volunteer):
        messages.error(request, "You don't have access to end this session.")
        return redirect("volunteer_dashboard" if hasattr(request.user, 'volunteer') else "user_dashboard")

    companion_request.status = "Completed"
    companion_request.save(update_fields=["status"])

    messages.success(request, "Session ended.")
    return redirect("volunteer_companion_sessions" if hasattr(request.user, 'volunteer') else "user_dashboard")

@login_required
def update_volunteer_location(request):
    if request.method == "POST" and hasattr(request.user, 'volunteer'):
        lat = request.POST.get("latitude")
        lng = request.POST.get("longitude")

        if lat and lng:
            volunteer = request.user.volunteer
            volunteer.latitude = float(lat)
            volunteer.longitude = float(lng)
            volunteer.last_location_update = timezone.now()
            volunteer.save(update_fields=["latitude", "longitude", "last_location_update"])
            messages.success(request, "Location updated successfully.")
        else:
            messages.error(request, "Could not read location from browser.")

    return redirect("volunteer_dashboard")

def profile(request):
    user_profile = get_object_or_404(Profile, user=request.user)
    return render(request, 'guardianwebapp/profile.html', {'profile': user_profile})

@csrf_exempt
def save_location(request):

    if request.method != "POST":
        return JsonResponse({"success": False})

    try:
        data = json.loads(request.body)

        session = LiveWatchSession.objects.get(
            id=data["session_id"],
            status="ACTIVE"
        )

        GPSPoint.objects.create(
            session=session,
            latitude=data["latitude"],
            longitude=data["longitude"],
            accuracy=data.get("accuracy", 0)
        )

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })

from .models import LiveWatchSession, SessionStatus

def start_session(request):
    if request.method == "POST":
        from_location = request.POST.get("origin")
        to_location = request.POST.get("destination")

        origin_lat = request.POST.get("origin_lat")
        origin_lng = request.POST.get("origin_lng")
        dest_lat = request.POST.get("dest_lat")
        dest_lng = request.POST.get("dest_lng")

        session = LiveWatchSession.objects.create(
            user=request.user,
            status=SessionStatus.ACTIVE,
            origin_name=from_location,
            destination_name=to_location,
            origin_lat=float(origin_lat) if origin_lat else None,
            origin_lng=float(origin_lng) if origin_lng else None,
            destination_lat=float(dest_lat) if dest_lat else None,
            destination_lng=float(dest_lng) if dest_lng else None,
        )

        return redirect("track", session_id=session.id)

    return render(request, "guardianwebapp/share_location.html")

@login_required
def track_view(request, session_id):
    session = get_object_or_404(
        LiveWatchSession, pk=session_id, user=request.user
    )
    checkpoints = list(session.checkpoints.all().values())
    return render(request, "guardianwebapp/track.html", {
        "session":        session,
        "checkpoints_json": json.dumps(checkpoints),
        "ws_url":         f"/ws/guardianwebapp/track/{session.pk}/",
    })


@require_POST
def end_session(request, session_id):
    session = get_object_or_404(LiveWatchSession, pk=session_id, user=request.user)
    session.end_session(SessionStatus.SAFE)
    messages.success(request, "Journey marked as completed safely.")
    return redirect("user_dashboard")

@require_POST
def update_expected_duration(request, session_id):
    session = get_object_or_404(LiveWatchSession, pk=session_id, user=request.user)
    minutes = request.POST.get("minutes")
    if minutes:
        session.expected_duration = int(float(minutes))
        session.save(update_fields=["expected_duration"])
    return JsonResponse({"success": True})

@login_required
def session_history(request):
    sessions = LiveWatchSession.objects.filter(user=request.user).order_by("-started_at")
    return render(request, "guardianwebapp/history.html", {"sessions": sessions})


@login_required
def sos_sent(request):
    from .models import EmergencyAlert, DangerEvent, DangerLevel, Profile, GuardianWatchLink, Volunteer
    from django.utils import timezone

    # GET with an existing alert_id in query string = just show confirmation, don't create anything
    alert_id = request.GET.get("alert_id")
    if request.method == "GET" and alert_id:
        alert = get_object_or_404(EmergencyAlert, id=alert_id, user=request.user)
        return render(request, "guardianwebapp/sos_sent.html", build_sos_context(request, alert))

    # Otherwise (panic button GET with no alert_id, OR shake POST) — create a new alert
    active_session = LiveWatchSession.objects.filter(
        user=request.user, status=SessionStatus.ACTIVE
    ).first()

    latitude, longitude = 12.9716, 77.5946
    if active_session:
        latest_gps = GPSPoint.objects.filter(session=active_session).order_by('-recorded_at').first()
        if latest_gps:
            latitude = latest_gps.latitude
            longitude = latest_gps.longitude

    posted_lat = request.POST.get("latitude")
    posted_lng = request.POST.get("longitude")
    if posted_lat and posted_lng:
        latitude, longitude = float(posted_lat), float(posted_lng)

    voice_note = request.FILES.get("voice_note")
    transcript = request.POST.get("transcript", "").strip()

    alert = EmergencyAlert.objects.create(
        user=request.user,
        session=active_session,
        latitude=latitude,
        longitude=longitude,
        status="Sent",
        voice_note=voice_note,
        transcript=transcript
    )

    if active_session:
        active_session.sos_triggered = True
        active_session.sos_at = alert.created_at
        active_session.status = SessionStatus.DANGER
        active_session.save(update_fields=["sos_triggered", "sos_at", "status"])

        DangerEvent.objects.create(
            session=active_session,
            trigger="sos",
            level=DangerLevel.CRITICAL,
            description="SOS alert triggered manually by user from dashboard.",
            latitude=latitude,
            longitude=longitude,
        )

    context = build_sos_context(request, alert)

    # Shake flow (AJAX POST) — return JSON with the alert id, don't render/redirect here
    if request.method == "POST":
        return JsonResponse({"success": True, "alert_id": alert.id})

    # Panic button (plain GET, no alert_id yet) — render confirmation directly
    return render(request, "guardianwebapp/sos_sent.html", context)


def build_sos_context(request, alert):
    from .models import Profile, GuardianWatchLink, Volunteer
    from django.utils import timezone

    now = timezone.now()
    guardians_list = []
    links = GuardianWatchLink.objects.filter(user=request.user)

    for link in links:
        name = link.guardian.username if link.guardian else (link.viewer_name or "External Guardian")
        is_online = False
        phone = None

        if link.guardian:
            is_online = bool(link.guardian.last_login and (now - link.guardian.last_login).total_seconds() < 3600)
            try:
                profile = Profile.objects.get(user=link.guardian)
                phone = profile.phone
            except Profile.DoesNotExist:
                phone = None
        else:
            phone = link.viewer_phone
            is_online = False

        notified_via = "not notified (no valid phone on file)"
        if phone and len(phone) == 10:
            try:
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                msg_body = (
                    f"CRITICAL SOS ALERT: {request.user.username} is in distress!\n"
                    f"Time: {timezone.localtime(alert.created_at).strftime('%d %b %Y, %I:%M %p')}\n"
                    f"Live location: https://www.openstreetmap.org/?mlat={alert.latitude}&mlon={alert.longitude}#map=17/{alert.latitude}/{alert.longitude}"
                )
                to_phone = "+91" + phone if not phone.startswith("+") else phone
                client.messages.create(body=msg_body, from_=settings.TWILIO_PHONE_NUMBER, to=to_phone)
                notified_via = "SMS sent"
                link.notified_sos = True
                link.save(update_fields=["notified_sos"])
            except Exception as ex:
                print(f"Failed to send SMS to {name}: {ex}")
                notified_via = "SMS failed to send"

        guardians_list.append({"name": name, "status": notified_via, "is_online": is_online})

    volunteers_list = []
    for v in Volunteer.objects.select_related('user').all():
        is_online = bool(v.user.last_login and (now - v.user.last_login).total_seconds() < 3600)
        volunteers_list.append({"name": v.user.username, "is_online": is_online, "is_available": v.is_available})

    return {
        "alert_time": timezone.localtime(alert.created_at),
        "latitude": alert.latitude,
        "longitude": alert.longitude,
        "location": reverse_geocode(alert.latitude, alert.longitude),
        "guardians": guardians_list,
        "volunteers": volunteers_list,
        "alert": alert,
    }

@login_required
def sos_alerts_list(request):
    from .models import EmergencyAlert, GuardianWatchLink, Volunteer

    # People this guardian watches
    watched_user_ids = GuardianWatchLink.objects.filter(
        guardian=request.user
    ).values_list('user_id', flat=True)

    # Is this logged-in user also a volunteer?
    is_volunteer = Volunteer.objects.filter(user=request.user).exists()

    if is_volunteer:
        all_alerts = EmergencyAlert.objects.all().order_by('-created_at')
    else:
        all_alerts = EmergencyAlert.objects.filter(
            user_id__in=watched_user_ids
        ).order_by('-created_at')

    active_alerts = []
    history_alerts = []

    for alert in all_alerts:
        taken_by = None
        if alert.accepted_by_guardian:
            taken_by = f"Guardian: {alert.accepted_by_guardian.username}"
        elif alert.accepted_by:
            taken_by = f"Volunteer: {alert.accepted_by.user.username}"

        item = {
            "id": alert.id,
            "username": alert.user.username,
            "created_at": alert.created_at,
            "address": alert.address,
            "latitude": alert.latitude,
            "longitude": alert.longitude,
            "taken_by": taken_by,
            "can_accept": taken_by is None,
            "voice_note_url": alert.voice_note.url if alert.voice_note else None,
            "transcript": alert.transcript,
        }

        if taken_by is None:
            active_alerts.append(item)
        else:
            history_alerts.append(item)

    return render(request, "guardianwebapp/sos_alerts_list.html", {
        "active_alerts": active_alerts,
        "history_alerts": history_alerts,
    })

@login_required
def sos_history_view(request):
    from .models import EmergencyAlert
    alerts = EmergencyAlert.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "guardianwebapp/sos_history.html", {"sos_history": alerts})

from django.core.files.base import ContentFile

@login_required
def attach_voice_note(request, alert_id):
    if request.method == "POST":
        alert = get_object_or_404(EmergencyAlert, id=alert_id, user=request.user)
        voice_note = request.FILES.get("voice_note")
        transcript = request.POST.get("transcript", "").strip()

        if voice_note:
            # Force correct content type — Django/mimetypes guesses 'video/webm' by default
            voice_note.content_type = "audio/webm"
            alert.voice_note = voice_note

        if transcript:
            alert.transcript = transcript

        alert.save(update_fields=["voice_note", "transcript"])
        return JsonResponse({"success": True})

    return JsonResponse({"error": "Invalid request"}, status=400)
    
@login_required
def accept_sos_alert(request, alert_id):
    from .models import EmergencyAlert, Volunteer

    alert = get_object_or_404(EmergencyAlert, id=alert_id)

    # Already taken by someone — don't allow double accept
    if alert.accepted_by_guardian or alert.accepted_by:
        messages.error(request, "This alert has already been accepted.")
        return redirect('sos_alerts_list')

    volunteer = Volunteer.objects.filter(user=request.user).first()

    if volunteer:
        alert.accepted_by = volunteer
        alert.save(update_fields=["accepted_by"])
        messages.success(request, "You've accepted this alert as a volunteer.")
    else:
        alert.accepted_by_guardian = request.user
        alert.save(update_fields=["accepted_by_guardian"])
        messages.success(request, "You've accepted this alert as a guardian.")

    alert.status = "Accepted"
    alert.save(update_fields=["status"])

    # Redirect to live tracking page for this alert's session
    if alert.session:
        return redirect('live_tracking', session_id=alert.session.id)

    messages.warning(request, "No active live session found for this alert.")
    return redirect('sos_alerts_list')

import requests

def reverse_geocode(lat, lng):
    """Convert lat/lng to a human-readable address using free Nominatim API."""
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "json", "lat": lat, "lon": lng},
            headers={"User-Agent": "GuardianWebApp/1.0"},
            timeout=5
        )
        data = response.json()
        return data.get("display_name", f"Lat: {lat:.4f}, Lng: {lng:.4f}")
    except Exception:
        return f"Lat: {lat:.4f}, Lng: {lng:.4f}"

from .models import LiveWatchSession, GuardianWatchLink
from django.contrib.auth.models import User
from django.db.models import Q

def add_guardian(request, session_id):
    from django.contrib.auth.models import User

    session = get_object_or_404(LiveWatchSession, id=session_id)

    if request.method == "POST":
        guardian_name = request.POST.get("guardian_username", "").strip()
        guardian_phone = request.POST.get("guardian_phone", "").strip()

        if not guardian_name:
            messages.error(request, "Guardian name is required.")
            return redirect("add_guardian", session_id=session.id)

        # Digits only, exactly 10 digits — no letters, symbols, spaces, or unicode digits
        if not re.fullmatch(r'\d{10}', guardian_phone, re.ASCII):
            messages.error(request, "Phone number must contain exactly 10 digits only.")
            return redirect("add_guardian", session_id=session.id)

        registered_user = User.objects.filter(username__iexact=guardian_name).first()

        if registered_user:
            if GuardianWatchLink.objects.filter(session=session, guardian=registered_user).exists():
                messages.error(request, "Guardian already exists.")
                return redirect("add_guardian", session_id=session.id)
        else:
            if GuardianWatchLink.objects.filter(
                session=session,
                viewer_name__iexact=guardian_name,
                viewer_phone=guardian_phone,
            ).exists():
                messages.error(request, "Guardian already exists.")
                return redirect("add_guardian", session_id=session.id)

        if registered_user:
            GuardianWatchLink.objects.create(
                session=session,
                user=request.user,
                guardian=registered_user,
                viewer_name=guardian_name,
                viewer_phone=guardian_phone,
            )
            messages.success(request, f"{guardian_name} added as a registered guardian (dashboard access enabled).")
        else:
            GuardianWatchLink.objects.create(
                session=session,
                user=request.user,
                viewer_name=guardian_name,
                viewer_phone=guardian_phone,
            )
            messages.success(request, f"{guardian_name} added as an external guardian (SMS alerts only).")

        return redirect("user_dashboard")

    return render(
        request,
        "guardianwebapp/add_guardian.html",
        #{"session": session}
    )


def remove_guardian(request, guardian_id):
    guardian = get_object_or_404(GuardianWatchLink, id=guardian_id)
    guardian.delete()
    return redirect("user_dashboard")

@login_required
def guardian_emergency_alerts(request):
    from .models import GuardianWatchLink, EmergencyAlert

    # Get all users this guardian is linked to (distinct)
    watched_user_ids = GuardianWatchLink.objects.filter(
        guardian=request.user
    ).values_list('user_id', flat=True).distinct()   # <-- fixed: was session__user_id

    current_alerts = EmergencyAlert.objects.filter(
        user_id__in=watched_user_ids,
        resolved=False
    ).select_related('user', 'accepted_by__user', 'accepted_by_guardian').order_by('-created_at')

    past_alerts = EmergencyAlert.objects.filter(
        user_id__in=watched_user_ids,
        resolved=True
    ).select_related('user', 'accepted_by__user', 'accepted_by_guardian').order_by('-created_at')

    return render(request, "guardianwebapp/guardian_emergency_alerts.html", {
        "current_alerts": current_alerts,
        "past_alerts": past_alerts,
    })


@login_required
def mark_alert_resolved(request, alert_id):
    from .models import EmergencyAlert

    alert = get_object_or_404(EmergencyAlert, id=alert_id)
    alert.resolved = True
    alert.resolved_at = timezone.now()
    alert.save(update_fields=["resolved", "resolved_at"])

    messages.success(request, "Alert marked as resolved.")
    return redirect("guardian_emergency_alerts")

@login_required
def guardian_accept_alert(request, alert_id):
    from .models import EmergencyAlert

    alert = get_object_or_404(EmergencyAlert, id=alert_id)

    if alert.status == "Sent" and not alert.accepted_by and not alert.accepted_by_guardian:
        alert.status = "Accepted"
        alert.accepted_by_guardian = request.user
        alert.save(update_fields=["status", "accepted_by_guardian"])
        messages.success(request, "You accepted this alert.")
    else:
        messages.error(request, "This alert has already been accepted.")

    return redirect("guardian_emergency_alerts")

from .models import CompanionChatMessage
@login_required
def companion_view(request):

    if request.method == "GET":
        return render(request, "guardianwebapp/companion_mode.html")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "start_request":
            companion_request = CompanionRequest.objects.create(
                user=request.user,
                volunteer=None,
                status="Pending"
            )
            return redirect("companion_waiting", request_id=companion_request.id)

        elif action == "chat_message":
            request_id = request.POST.get("request_id")
            message = request.POST.get("message", "").strip()

            if not request_id or not message:
                return JsonResponse({"note": "Message could not be sent."}, status=400)

            companion_request = get_object_or_404(CompanionRequest, id=request_id)

            is_requester = companion_request.user == request.user
            is_assigned_volunteer = (
                hasattr(request.user, 'volunteer') and
                companion_request.volunteer == request.user.volunteer
            )

            if not (is_requester or is_assigned_volunteer):
                return JsonResponse({"note": "Access denied."}, status=403)

            sender_type = "user" if is_requester else "volunteer"

            if companion_request.status == "AI_Mode":
                recent_messages = list(
                    companion_request.messages
                    .filter(sender_type__in=["user", "ai"])
                    .order_by("-created_at")[:10]
                )
                history = [
                    {
                        "role": "user" if item.sender_type == "user" else "model",
                        "text": item.text,
                    }
                    for item in reversed(recent_messages)
                ]

                user_message = CompanionChatMessage.objects.create(
                    companion_request=companion_request,
                    sender_type=sender_type,
                    text=message,
                )

                reply = get_ai_companion_reply(message, history=history)

                ai_message = CompanionChatMessage.objects.create(
                    companion_request=companion_request,
                    sender_type="ai",
                    text=reply,
                )

                return JsonResponse({
                    "reply": reply,
                    "user_id": user_message.id,
                    "id": ai_message.id,
                })

            elif companion_request.status == "Accepted":
                msg_obj = CompanionChatMessage.objects.create(
                    companion_request=companion_request,
                    sender_type=sender_type,
                    text=message,
                )
                return JsonResponse({"id": msg_obj.id, "sent": True})

            else:
                return JsonResponse({"note": "Still waiting for a volunteer to accept..."})

    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
def companion_waiting(request, request_id):
    companion_request = get_object_or_404(CompanionRequest, id=request_id, user=request.user)
    return render(request, "guardianwebapp/request_sent.html", {"request_obj": companion_request})


@login_required
def companion_status_check(request, request_id):
    companion_request = get_object_or_404(CompanionRequest, id=request_id, user=request.user)
    return JsonResponse({
        "status": companion_request.status,
        "volunteer": companion_request.volunteer.user.username if companion_request.volunteer else None,
    })


@login_required
def companion_timeout(request, request_id):
    companion_request = get_object_or_404(CompanionRequest, id=request_id, user=request.user)
    if companion_request.status == "Pending":
        companion_request.status = "AI_Mode"
        companion_request.save(update_fields=["status"])
    return JsonResponse({"status": companion_request.status})


@login_required
def companion_chat(request, request_id):
    companion_request = get_object_or_404(CompanionRequest, id=request_id)

    is_requester = companion_request.user == request.user
    is_assigned_volunteer = (
        hasattr(request.user, 'volunteer') and
        companion_request.volunteer == request.user.volunteer
    )

    if not (is_requester or is_assigned_volunteer):
        messages.error(request, "You don't have access to this session.")
        return redirect("volunteer_dashboard" if hasattr(request.user, 'volunteer') else "user_dashboard")

    if companion_request.status not in ("Accepted", "AI_Mode"):
        messages.error(request, "This companion session isn't active yet.")
        return redirect("companion_waiting", request_id=request_id)

    return render(request, "guardianwebapp/companion_chat.html", {
        "request_obj": companion_request,
        "is_requester": is_requester,
    })


@login_required
def accept_companion_request(request, request_id):
    if not hasattr(request.user, 'volunteer'):
        messages.error(request, "You are not registered as a volunteer.")
        return redirect("user_dashboard")

    volunteer = request.user.volunteer

    updated = CompanionRequest.objects.filter(id=request_id, status="Pending").update(
        volunteer=volunteer,
        status="Accepted",
        accepted_at=timezone.now()
    )

    if updated:
        messages.success(request, "You accepted the companion request.")
    else:
        messages.error(request, "This request was already accepted by another volunteer or timed out.")

    return redirect("volunteer_dashboard")

@login_required
def companion_messages_fetch(request, request_id):
    companion_request = get_object_or_404(CompanionRequest, id=request_id)

    is_requester = companion_request.user == request.user
    is_assigned_volunteer = (
        hasattr(request.user, 'volunteer') and
        companion_request.volunteer == request.user.volunteer
    )
    if not (is_requester or is_assigned_volunteer):
        return JsonResponse({"error": "Access denied"}, status=403)

    after_id = request.GET.get("after", 0)
    msgs = companion_request.messages.filter(id__gt=after_id).order_by("created_at")

    return JsonResponse({
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "text": m.text,
                "time": m.created_at.strftime("%H:%M"),
            }
            for m in msgs
        ]
    })

import google.generativeai as genai
from django.conf import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

def get_ai_companion_reply(message, history=None):
    history = history or []

    emergency_words = [
        "help", "emergency", "danger", "attack", "kidnap", "kidnapped",
        "follow", "following", "unsafe", "robbery", "panic",
        "murder", "save me", "police", "thief", "abuse"
    ]
    if any(word in message.lower() for word in emergency_words):
        return ("🚨 It sounds like you may be in danger. Please press the SOS button "
                "immediately so your guardians can be alerted. If possible, move to a safe place.")

    model = genai.GenerativeModel(
        "gemini-flash-latest",
        system_instruction=(
            "You are a warm, supportive AI companion for someone using a personal safety app "
            "who requested company because no volunteer was immediately available. Be empathetic, "
            "conversational, and natural. Keep responses fairly short (2-4 sentences). "
            "If the person indicates they are in immediate danger, being followed, attacked, or "
            "otherwise unsafe, clearly tell them to press the SOS button in the app."
        ),
    )

    try:
        contents = [
            {"role": item["role"], "parts": [item["text"]]}
            for item in history
            if item.get("role") in ("user", "model") and item.get("text")
        ]
        contents.append({"role": "user", "parts": [message]})
        response = model.generate_content(contents)
        return response.text or "I'm here with you. Could you tell me a little more?"
    except Exception as ex:
        print(f"Gemini API error: {ex}")
        return "I'm having trouble responding right now. If you're in danger, please press the SOS button immediately."


@login_required
def companion_timeout(request, request_id):
    companion_request = get_object_or_404(CompanionRequest, id=request_id, user=request.user)
    if companion_request.status == "Pending":
        companion_request.status = "AI_Mode"
        companion_request.save(update_fields=["status"])
    return JsonResponse({"status": companion_request.status})

def emergency_alert_view(request):
    from .models import EmergencyAlert

    pending_requests = (
        EmergencyAlert.objects
        .filter(status="Sent")
        .select_related('user')
        .prefetch_related('session__guardian_links', 'volunteers_notified__user')
        .order_by('-created_at')
    )

    accepted_requests = (
        EmergencyAlert.objects
        .filter(status="Accepted")
        .select_related('user', 'accepted_by__user')
        .prefetch_related('session__guardian_links', 'volunteers_notified__user')
        .order_by('-created_at')
    )

    return render(request, "guardianwebapp/emergency_alert.html", {
        "requests": pending_requests,        # kept as-is, so nothing else that reuses this breaks
        "accepted_requests": accepted_requests,
    })

@login_required
def accept_emergency_request(request, request_id):
    if not hasattr(request.user, 'volunteer'):
        return JsonResponse({"error": "Not a volunteer"}, status=403)

    volunteer = request.user.volunteer
    alert = get_object_or_404(EmergencyAlert, id=request_id, status="Sent")

    updated = EmergencyAlert.objects.filter(id=request_id, accepted_by__isnull=True, accepted_by_guardian__isnull=True).update(
        status="Accepted",
        accepted_by=volunteer
    )

    if updated:
        return JsonResponse({"success": True, "accepted_by": volunteer.user.username})
    else:
        return JsonResponse({"success": False, "message": "Already accepted by someone else."})

@login_required
def volunteer_track_alert(request, alert_id):
    from .models import EmergencyAlert

    alert = get_object_or_404(
        EmergencyAlert, id=alert_id, accepted_by=request.user.volunteer
    )

    return render(request, "guardianwebapp/volunteer_track_alert.html", {
        "alert": alert,
    })
def travel_view(request):
    return render(request, "guardianwebapp/travel_monitoring.html")

def share_location(request):
    return render(request, "guardianwebapp/share_location.html")

def watch_by_code(request, share_code):
    from .models import LiveWatchSession

    session = get_object_or_404(LiveWatchSession, share_code=share_code)
    latest_location = session.gps_points.order_by('-recorded_at').first()

    return render(request, "guardianwebapp/watch_by_code.html", {
        "session": session,
        "location": latest_location,
    })

@login_required
def travel_monitoring(request):
    from .models import GuardianWatchLink, LiveWatchSession

    watched_user_ids = GuardianWatchLink.objects.filter(
        guardian=request.user
    ).values_list('session__user_id', flat=True).distinct()

    active_journeys = LiveWatchSession.objects.filter(
        user_id__in=watched_user_ids, status=SessionStatus.ACTIVE
    ).select_related('user').order_by('-started_at')

    past_journeys = LiveWatchSession.objects.filter(
        user_id__in=watched_user_ids
    ).exclude(status=SessionStatus.ACTIVE).select_related('user').order_by('-started_at')

    return render(request, "guardianwebapp/travel_monitoring.html", {
        "active_journeys": active_journeys,
        "past_journeys": past_journeys,
    })


@login_required
def toggle_availability(request):
    if not hasattr(request.user, 'volunteer'):
        messages.error(request, "You are not registered as a volunteer.")
        return redirect("user_dashboard")

    volunteer = request.user.volunteer

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "available":
            volunteer.is_available = True
            volunteer.save(update_fields=["is_available"])
            messages.success(request, "You are now marked as Available.")

        elif action == "unavailable":
            volunteer.is_available = False
            volunteer.save(update_fields=["is_available"])
            messages.success(request, "You are now marked as Unavailable.")

    return redirect("volunteer_dashboard")