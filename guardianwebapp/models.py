from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import math


class Profile(models.Model):

    ROLE_CHOICES = [
        ('user', 'User'),
        ('guardian', 'Guardian'),
        ('volunteer', 'Volunteer'),
    ]

    user = models.OneToOneField( User,on_delete=models.CASCADE)
    phone = models.CharField(max_length=10,unique=True)
    role = models.CharField(max_length=20,choices=ROLE_CHOICES)
    address=models.CharField(max_length=255,blank=True)
    profile_picture=models.ImageField(upload_to='profile_pictures/',blank=True,null=True)

    def __str__(self):
        return self.user.username


class SessionStatus:
    ACTIVE   = "active"
    PAUSED   = "paused"
    SAFE     = "safe"       # user pressed "Arrived Safe"
    EXPIRED  = "expired"   # auto-expired after timeout
    DANGER   = "danger"    # danger auto-detected

    CHOICES = [
        (ACTIVE,  "Active"),
        (PAUSED,  "Paused"),
        (SAFE,    "Safe"),
        (EXPIRED, "Expired"),
        (DANGER,  "Danger"),
    ]


class DangerLevel:
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"

    CHOICES = [
        (LOW,      "Low"),
        (MEDIUM,   "Medium"),
        (HIGH,     "High"),
        (CRITICAL, "Critical"),
    ]


class LiveWatchSession(models.Model):
    user         = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="watch_sessions"
    )
    title        = models.CharField(max_length=200, default="My Journey")

    # Route details
    origin_name      = models.CharField(max_length=255, blank=True)
    destination_name = models.CharField(max_length=255, blank=True)
    origin_lat       = models.FloatField(null=True, blank=True)
    origin_lng       = models.FloatField(null=True, blank=True)
    destination_lat  = models.FloatField(null=True, blank=True)
    destination_lng  = models.FloatField(null=True, blank=True)

    # Timing
    started_at        = models.DateTimeField(default=timezone.now)
    expected_duration = models.PositiveIntegerField(
        default=60, help_text="Expected duration in minutes"
    )
    ended_at          = models.DateTimeField(null=True, blank=True)

    status     = models.CharField(
        max_length=20, choices=SessionStatus.CHOICES, default=SessionStatus.ACTIVE
    )
    share_code = models.CharField(
        max_length=12, unique=True, blank=True,
        help_text="6-char code guardians use to follow this session"
    )

    # Danger / SOS
    sos_triggered = models.BooleanField(default=False)
    sos_at        = models.DateTimeField(null=True, blank=True)
    sos_note      = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user.username} — {self.title} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.share_code:
            import secrets
            self.share_code = secrets.token_urlsafe(6)[:8].upper()
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status == SessionStatus.ACTIVE

    @property
    def duration_elapsed(self):
        """Minutes elapsed since session start."""
        end = self.ended_at or timezone.now()
        return int((end - self.started_at).total_seconds() / 60)

    @property
    def is_overdue(self):
        return (
            self.is_active
            and self.duration_elapsed > self.expected_duration + 10
        )

    def end_session(self, status=SessionStatus.SAFE):
        self.status   = status
        self.ended_at = timezone.now()
        self.save(update_fields=["status", "ended_at"])

class GPSPoint(models.Model):
    """
    Individual GPS ping from the user's device.
    Stored every N seconds while session is active.
    """
    session   = models.ForeignKey(
        LiveWatchSession, on_delete=models.CASCADE, related_name="gps_points"
    )
    latitude  = models.FloatField()
    longitude = models.FloatField()
    accuracy  = models.FloatField(null=True, blank=True, help_text="Accuracy in metres")
    altitude  = models.FloatField(null=True, blank=True)
    speed     = models.FloatField(null=True, blank=True, help_text="Speed in m/s")
    heading   = models.FloatField(null=True, blank=True, help_text="Degrees from North")
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["recorded_at"]
        indexes  = [models.Index(fields=["session", "recorded_at"])]

    def __str__(self):
        return f"({self.latitude:.4f}, {self.longitude:.4f}) @ {self.recorded_at:%H:%M:%S}"

    @staticmethod
    def haversine(lat1, lng1, lat2, lng2):
        """Returns distance in metres between two lat/lng pairs."""
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lng2 - lng1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class Checkpoint(models.Model):
    """
    Named waypoints the user wants to confirm passing through.
    Guardian sees ✓ / ✗ in real time.
    """
    session     = models.ForeignKey(
        LiveWatchSession, on_delete=models.CASCADE, related_name="checkpoints"
    )
    name        = models.CharField(max_length=200)
    latitude    = models.FloatField()
    longitude   = models.FloatField()
    radius_m    = models.PositiveIntegerField(
        default=100, help_text="Auto-confirm radius in metres"
    )
    order       = models.PositiveSmallIntegerField(default=0)

    # Confirmation
    confirmed     = models.BooleanField(default=False)
    confirmed_at  = models.DateTimeField(null=True, blank=True)
    confirmed_how = models.CharField(
        max_length=10,
        choices=[("auto", "Auto (GPS)"), ("manual", "Manual")],
        default="manual",
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        tick = "✓" if self.confirmed else "○"
        return f"{tick} {self.name} ({self.session})"

    def try_auto_confirm(self, gps_point: GPSPoint) -> bool:
        """Returns True if the GPS point is within this checkpoint's radius."""
        dist = GPSPoint.haversine(
            gps_point.latitude, gps_point.longitude,
            self.latitude, self.longitude
        )
        if dist <= self.radius_m and not self.confirmed:
            self.confirmed     = True
            self.confirmed_at  = gps_point.recorded_at
            self.confirmed_how = "auto"
            self.save(update_fields=["confirmed", "confirmed_at", "confirmed_how"])
            return True
        return False

class DangerEvent(models.Model):
    """
    Auto-detected or manually triggered danger signals.
    Each event can escalate over time if unacknowledged.
    """
    TRIGGER_CHOICES = [
        ("sos",          "SOS Button"),
        ("no_movement",  "No Movement Detected"),
        ("speed_drop",   "Sudden Speed Drop"),
        ("route_deviate","Route Deviation"),
        ("overdue",      "Journey Overdue"),
        ("checkpoint_missed", "Checkpoint Missed"),
    ]

    session     = models.ForeignKey(
        LiveWatchSession, on_delete=models.CASCADE, related_name="danger_events"
    )
    trigger     = models.CharField(max_length=30, choices=TRIGGER_CHOICES)
    level       = models.CharField(
        max_length=10, choices=DangerLevel.CHOICES, default=DangerLevel.MEDIUM
    )
    description = models.TextField(blank=True)
    latitude    = models.FloatField(null=True, blank=True)
    longitude   = models.FloatField(null=True, blank=True)

    # Resolution
    acknowledged    = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="acknowledged_dangers"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved        = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.level.upper()}] {self.get_trigger_display()} — {self.session}"

    def acknowledge(self, guardian_user):
        self.acknowledged    = True
        self.acknowledged_by = guardian_user
        self.acknowledged_at = timezone.now()
        self.save(update_fields=["acknowledged", "acknowledged_by", "acknowledged_at"])

class GuardianWatchLink(models.Model):
    session  = models.ForeignKey(
        LiveWatchSession, on_delete=models.CASCADE, related_name="guardian_links",
        null=True, blank=True   # <-- now optional, kept only for historical reference
    )
    user = models.ForeignKey(              # <-- NEW: guardian now belongs to the account permanently
        User, on_delete=models.CASCADE, related_name="my_guardians",
        null=True, blank=True   # temporarily nullable so migration doesn't crash on existing rows
    )
    guardian = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="watching_sessions",
        null=True, blank=True,
    )
    # For non-registered viewers (link/code share)
    viewer_name  = models.CharField(max_length=100, blank=True)
    viewer_email = models.EmailField(blank=True)
    viewer_phone = models.CharField(max_length=15, blank=True)

    notified_sos     = models.BooleanField(default=False)
    notified_overdue = models.BooleanField(default=False)

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "guardian")]   # <-- changed from ("session", "guardian")

    def __str__(self):
        who = self.guardian.username if self.guardian else self.viewer_name or "external"
        owner = self.user.username if self.user else "unknown"
        return f"{who} watching {owner}" 

class PoliceStation(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.name


class EmergencyAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session = models.ForeignKey(
        'LiveWatchSession', on_delete=models.CASCADE,
        related_name='emergency_alerts', null=True, blank=True
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    address = models.CharField(max_length=255, blank=True, null=True)
    priority = models.CharField(max_length=20, default="High")
    status = models.CharField(max_length=20, default="Sent")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    volunteers_notified = models.ManyToManyField('Volunteer', related_name='alerts_notified', blank=True)
    accepted_by = models.ForeignKey('Volunteer', on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_alerts')
    accepted_by_guardian = models.ForeignKey(User, on_delete=models.SET_NULL,null=True, blank=True, related_name='guardian_accepted_alerts')
    voice_note = models.FileField(upload_to='sos_audio/', null=True, blank=True)

    transcript = models.TextField(blank=True, null=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalated_to_police = models.BooleanField(default=False)
    nearest_police_station = models.ForeignKey(
        PoliceStation, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.user.username} - {self.created_at}" 
    
class Volunteer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_available = models.BooleanField(default=False)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    last_location_update = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.user.username
    
class CompanionRequest(models.Model):

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("AI_Mode", "AI_Mode"),      # <-- new: auto-switches here after 2 min timeout
        ("Rejected", "Rejected"),
        ("Completed", "Completed"),  # optional, for when the session ends
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="companion_requests"
    )

    volunteer = models.ForeignKey(
        Volunteer,
        on_delete=models.CASCADE,
        related_name="assigned_requests",
        null=True, blank=True     # <-- changed: unassigned until a volunteer accepts
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending"
    )

    requested_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)   # <-- new: track when accepted

    def __str__(self):
        return f"{self.user.username} → {self.volunteer.user.username if self.volunteer else 'Unassigned'} ({self.status})"
    
class CompanionChatMessage(models.Model):
    SENDER_CHOICES = [
        ("user", "User"),
        ("volunteer", "Volunteer"),
        ("ai", "AI"),
    ]

    companion_request = models.ForeignKey(
        CompanionRequest, on_delete=models.CASCADE, related_name="messages"
    )
    sender_type = models.CharField(max_length=10, choices=SENDER_CHOICES)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.sender_type}] {self.text[:30]}"
    
class UserGuardian(models.Model):
    """A guardian permanently linked to a user, independent of any session."""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="guardians"
    )
    guardian = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="wards",
        null=True, blank=True
    )
    # For guardians who aren't registered users yet
    viewer_name = models.CharField(max_length=100, blank=True)
    viewer_phone = models.CharField(max_length=15, blank=True)
    viewer_email = models.EmailField(blank=True)

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "guardian")]

    def __str__(self):
        who = self.guardian.username if self.guardian else self.viewer_name or "external"
        return f"{who} guards {self.user.username}"
    
