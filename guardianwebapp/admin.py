from django.contrib import admin
from .models import LiveWatchSession, GPSPoint, Checkpoint, DangerEvent, GuardianWatchLink


@admin.register(LiveWatchSession)
class LiveWatchSessionAdmin(admin.ModelAdmin):
    list_display  = ("title", "user", "status", "started_at", "is_overdue", "sos_triggered")
    list_filter   = ("status", "sos_triggered")
    search_fields = ("user__username", "title", "share_code")
    readonly_fields = ("share_code", "started_at", "ended_at")


@admin.register(GPSPoint)
class GPSPointAdmin(admin.ModelAdmin):
    list_display  = ("session", "latitude", "longitude", "speed", "recorded_at")
    list_filter   = ("session__status",)
    readonly_fields = ("recorded_at",)


@admin.register(Checkpoint)
class CheckpointAdmin(admin.ModelAdmin):
    list_display  = ("name", "session", "confirmed", "confirmed_at", "confirmed_how")
    list_filter   = ("confirmed",)


@admin.register(DangerEvent)
class DangerEventAdmin(admin.ModelAdmin):
    list_display  = ("trigger", "level", "session", "acknowledged", "resolved", "created_at")
    list_filter   = ("level", "trigger", "acknowledged", "resolved")
    readonly_fields = ("created_at",)


@admin.register(GuardianWatchLink)
class GuardianWatchLinkAdmin(admin.ModelAdmin):
    list_display = ("session", "guardian", "viewer_name", "joined_at")


# Register your models here.
