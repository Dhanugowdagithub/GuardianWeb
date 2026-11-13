"""
livewatch/danger_engine.py
──────────────────────────
Analyses GPS points for a session and raises DangerEvents when
anomalies are detected.  Called after every GPS ping.
"""

from django.utils import timezone
from datetime import timedelta
import math

from .models import (
    GPSPoint, DangerEvent, LiveWatchSession,
    DangerLevel, SessionStatus, Checkpoint,
)


# ─── Tuneable thresholds ──────────────────────────────────────────────────────

NO_MOVEMENT_WINDOW_MINUTES  = 5      # Stationary for this long → alert
NO_MOVEMENT_RADIUS_METRES   = 30     # "Stationary" if within this radius

SPEED_DROP_WINDOW_SECONDS   = 60     # Compare speed over this window
SPEED_DROP_THRESHOLD_MS     = 1.5   # Diff in m/s that counts as "sudden"

ROUTE_DEVIATION_METRES      = 500    # How far off the straight-line route = deviation
CHECKPOINT_OVERDUE_MINUTES  = 15    # Minutes past expected arrival at checkpoint = alert

OVERDUE_GRACE_MINUTES       = 10    # Extra grace after expected_duration before alert


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _already_open(session, trigger):
    """True if an unresolved DangerEvent of this trigger already exists."""
    return DangerEvent.objects.filter(
        session=session, trigger=trigger, resolved=False
    ).exists()


def _create_danger(session, trigger, level, description, lat=None, lng=None):
    if _already_open(session, trigger):
        return None
    event = DangerEvent.objects.create(
        session=session,
        trigger=trigger,
        level=level,
        description=description,
        latitude=lat,
        longitude=lng,
    )
    # Escalate session status for HIGH / CRITICAL
    if level in (DangerLevel.HIGH, DangerLevel.CRITICAL):
        session.status = SessionStatus.DANGER
        session.save(update_fields=["status"])
    return event


def haversine(lat1, lng1, lat2, lng2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _point_to_segment_distance(px, py, ax, ay, bx, by):
    """Perpendicular distance from point P to segment AB (in degrees, approx)."""
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    # Convert degree difference → metres (rough, good enough for short segments)
    lat_m = (px - cx) * 111_320
    lng_m = (py - cy) * 111_320 * math.cos(math.radians(px))
    return math.hypot(lat_m, lng_m)


# ─── Individual detectors ────────────────────────────────────────────────────

def check_no_movement(session: LiveWatchSession, latest: GPSPoint):
    """
    If the last N minutes of points are all within NO_MOVEMENT_RADIUS_METRES
    of each other → stationary alert.
    """
    window_start = latest.recorded_at - timedelta(minutes=NO_MOVEMENT_WINDOW_MINUTES)
    recent = list(
        GPSPoint.objects.filter(
            session=session, recorded_at__gte=window_start
        ).values("latitude", "longitude")
    )
    if len(recent) < 3:
        return None  # Not enough data yet

    # Check if all points are within radius of the earliest in window
    anchor = recent[0]
    all_close = all(
        haversine(anchor["latitude"], anchor["longitude"], p["latitude"], p["longitude"])
        <= NO_MOVEMENT_RADIUS_METRES
        for p in recent[1:]
    )
    if all_close:
        return _create_danger(
            session,
            trigger="no_movement",
            level=DangerLevel.HIGH,
            description=(
                f"No significant movement detected for {NO_MOVEMENT_WINDOW_MINUTES} minutes. "
                f"User may be in distress."
            ),
            lat=latest.latitude,
            lng=latest.longitude,
        )
    return None


def check_sudden_speed_drop(session: LiveWatchSession, latest: GPSPoint):
    """
    Compare average speed in two consecutive windows.
    A sudden large drop (moving → stopped) can indicate an incident.
    """
    if latest.speed is None:
        return None

    window = timedelta(seconds=SPEED_DROP_WINDOW_SECONDS)
    now    = latest.recorded_at

    prev_points = list(
        GPSPoint.objects.filter(
            session=session,
            recorded_at__gte=now - 2 * window,
            recorded_at__lt=now - window,
        ).exclude(speed=None).values_list("speed", flat=True)
    )
    curr_points = list(
        GPSPoint.objects.filter(
            session=session,
            recorded_at__gte=now - window,
        ).exclude(speed=None).values_list("speed", flat=True)
    )

    if not prev_points or not curr_points:
        return None

    prev_avg = sum(prev_points) / len(prev_points)
    curr_avg = sum(curr_points) / len(curr_points)

    if prev_avg >= SPEED_DROP_THRESHOLD_MS and curr_avg < 0.3:
        return _create_danger(
            session,
            trigger="speed_drop",
            level=DangerLevel.MEDIUM,
            description=(
                f"Sudden speed drop detected: {prev_avg:.1f} m/s → {curr_avg:.1f} m/s. "
                f"Possible stop or incident."
            ),
            lat=latest.latitude,
            lng=latest.longitude,
        )
    return None


def check_route_deviation(session: LiveWatchSession, latest: GPSPoint):
    """
    If session has origin + destination, check whether the user has deviated
    from the straight-line corridor by more than ROUTE_DEVIATION_METRES.
    """
    if not all([
        session.origin_lat, session.origin_lng,
        session.destination_lat, session.destination_lng,
    ]):
        return None

    dist = _point_to_segment_distance(
        latest.latitude, latest.longitude,
        session.origin_lat, session.origin_lng,
        session.destination_lat, session.destination_lng,
    )

    if dist > ROUTE_DEVIATION_METRES:
        return _create_danger(
            session,
            trigger="route_deviate",
            level=DangerLevel.MEDIUM,
            description=(
                f"User is {dist:.0f}m off the expected route. "
                f"Possible detour or forced deviation."
            ),
            lat=latest.latitude,
            lng=latest.longitude,
        )
    return None


def check_overdue(session: LiveWatchSession):
    """Alert if journey has exceeded expected_duration + grace period."""
    elapsed = session.duration_elapsed
    limit   = session.expected_duration + OVERDUE_GRACE_MINUTES
    if elapsed > limit:
        return _create_danger(
            session,
            trigger="overdue",
            level=DangerLevel.HIGH,
            description=(
                f"Journey is {elapsed - session.expected_duration} minutes overdue. "
                f"Expected duration: {session.expected_duration} min."
            ),
        )
    return None


def check_checkpoint_auto_confirm(session: LiveWatchSession, latest: GPSPoint):
    """Auto-confirm checkpoints the user has entered."""
    confirmed = []
    pending = Checkpoint.objects.filter(session=session, confirmed=False)
    for cp in pending:
        if cp.try_auto_confirm(latest):
            confirmed.append(cp)
    return confirmed


# ─── Main entry point ────────────────────────────────────────────────────────

def run_all_checks(session: LiveWatchSession, latest: GPSPoint) -> dict:
    """
    Run every detector for a session after a new GPS point arrives.
    Returns a dict of results for the caller (view / WebSocket consumer) to use.
    """
    if not session.is_active:
        return {"skipped": True}

    results = {
        "no_movement":   check_no_movement(session, latest),
        "speed_drop":    check_sudden_speed_drop(session, latest),
        "route_deviate": check_route_deviation(session, latest),
        "overdue":       check_overdue(session),
        "confirmed_checkpoints": check_checkpoint_auto_confirm(session, latest),
    }

    danger_events = [v for k, v in results.items()
                     if v and isinstance(v, DangerEvent)]
    results["any_danger"] = bool(danger_events)
    results["events"]     = danger_events
    return results
