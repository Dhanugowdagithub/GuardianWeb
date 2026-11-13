"""
livewatch/consumers.py
──────────────────────
Django Channels WebSocket consumers.

Two consumers:
  1. UserTrackingConsumer  – user sends GPS pings, receives danger alerts
  2. GuardianWatchConsumer – guardian receives live location + events in real time
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .models import LiveWatchSession, GPSPoint, DangerEvent, SessionStatus
from .danger_engine import run_all_checks
from .serializers import (
    gps_point_to_dict, session_summary, danger_event_to_dict, checkpoint_to_dict
)


# ─── Group name helpers ───────────────────────────────────────────────────────

def session_group(session_id):
    return f"livewatch_session_{session_id}"


# ═════════════════════════════════════════════════════════════════════════════
# 1. User Tracking Consumer
#    URL: ws/livewatch/track/<session_id>/
# ═════════════════════════════════════════════════════════════════════════════

class UserTrackingConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = session_group(self.session_id)
        self.user       = self.scope["user"]

        # Auth: must be logged in and own the session
        session = await self._get_session()
        if not session or session.user_id != self.user.id:
            await self.close(code=4003)
            return

        self.session = session
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial state
        await self.send(json.dumps({
            "type":    "session_init",
            "session": await database_sync_to_async(session_summary)(session),
        }))

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ── Receive GPS ping from user's browser / mobile ────────────────────────
    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            await self._send_error("Invalid JSON")
            return

        msg_type = data.get("type")

        if msg_type == "gps_update":
            await self._handle_gps_update(data)

        elif msg_type == "sos":
            await self._handle_sos(data)

        elif msg_type == "arrived_safe":
            await self._handle_arrived_safe()

        elif msg_type == "checkpoint_confirm":
            await self._handle_checkpoint_confirm(data)

        else:
            await self._send_error(f"Unknown message type: {msg_type}")

    # ── GPS update ────────────────────────────────────────────────────────────
    async def _handle_gps_update(self, data):
        try:
            lat = float(data["latitude"])
            lng = float(data["longitude"])
        except (KeyError, ValueError, TypeError):
            await self._send_error("latitude and longitude are required numbers")
            return

        point = await self._save_gps_point(
            latitude=lat,
            longitude=lng,
            accuracy=data.get("accuracy"),
            altitude=data.get("altitude"),
            speed=data.get("speed"),
            heading=data.get("heading"),
        )

        # Run danger checks (sync → async wrapper)
        results = await database_sync_to_async(run_all_checks)(self.session, point)

        # Broadcast to all guardians watching this session
        broadcast = {
            "type":      "location_update",
            "point":     gps_point_to_dict(point),
            "any_danger": results.get("any_danger", False),
            "events":    [danger_event_to_dict(e) for e in results.get("events", [])],
            "confirmed_checkpoints": [
                checkpoint_to_dict(c)
                for c in results.get("confirmed_checkpoints", [])
            ],
        }
        await self.channel_layer.group_send(self.group_name, {
            "type":    "broadcast_message",
            "payload": broadcast,
        })

        # Ack back to user
        await self.send(json.dumps({
            "type":    "gps_ack",
            "any_danger": results.get("any_danger", False),
        }))

    # ── SOS ───────────────────────────────────────────────────────────────────
    async def _handle_sos(self, data):
        event = await self._trigger_sos(data.get("note", ""))
        payload = {
            "type":  "sos_alert",
            "event": danger_event_to_dict(event),
        }
        await self.channel_layer.group_send(self.group_name, {
            "type":    "broadcast_message",
            "payload": payload,
        })
        await self.send(json.dumps({"type": "sos_confirmed"}))

    # ── Arrived safe ─────────────────────────────────────────────────────────
    async def _handle_arrived_safe(self):
        await database_sync_to_async(self.session.end_session)(SessionStatus.SAFE)
        payload = {"type": "session_ended", "status": SessionStatus.SAFE}
        await self.channel_layer.group_send(self.group_name, {
            "type":    "broadcast_message",
            "payload": payload,
        })
        await self.close()

    # ── Manual checkpoint confirm ─────────────────────────────────────────────
    async def _handle_checkpoint_confirm(self, data):
        cp_id = data.get("checkpoint_id")
        if not cp_id:
            return
        cp = await self._confirm_checkpoint(cp_id)
        if cp:
            await self.channel_layer.group_send(self.group_name, {
                "type": "broadcast_message",
                "payload": {
                    "type":       "checkpoint_confirmed",
                    "checkpoint": checkpoint_to_dict(cp),
                },
            })

    # ── Channel layer handler (receives from group_send) ─────────────────────
    async def broadcast_message(self, event):
        await self.send(json.dumps(event["payload"]))

    # ── DB helpers ────────────────────────────────────────────────────────────
    @database_sync_to_async
    def _get_session(self):
        try:
            return LiveWatchSession.objects.get(pk=self.session_id)
        except LiveWatchSession.DoesNotExist:
            return None

    @database_sync_to_async
    def _save_gps_point(self, **kwargs):
        return GPSPoint.objects.create(session=self.session, **kwargs)

    @database_sync_to_async
    def _trigger_sos(self, note):
        from .models import DangerLevel
        self.session.sos_triggered = True
        self.session.sos_at        = timezone.now()
        self.session.sos_note      = note
        self.session.status        = SessionStatus.DANGER
        self.session.save(update_fields=["sos_triggered", "sos_at", "sos_note", "status"])
        return DangerEvent.objects.create(
            session=self.session,
            trigger="sos",
            level=DangerLevel.CRITICAL,
            description=f"SOS triggered by user. Note: {note}" if note else "SOS triggered by user.",
        )

    @database_sync_to_async
    def _confirm_checkpoint(self, cp_id):
        from .models import Checkpoint
        try:
            cp = Checkpoint.objects.get(pk=cp_id, session=self.session, confirmed=False)
            cp.confirmed     = True
            cp.confirmed_at  = timezone.now()
            cp.confirmed_how = "manual"
            cp.save()
            return cp
        except Checkpoint.DoesNotExist:
            return None

    async def _send_error(self, msg):
        await self.send(json.dumps({"type": "error", "message": msg}))


# ═════════════════════════════════════════════════════════════════════════════
# 2. Guardian Watch Consumer
#    URL: ws/livewatch/watch/<session_id>/
#         ws/livewatch/watch/code/<share_code>/
# ═════════════════════════════════════════════════════════════════════════════

class GuardianWatchConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        kwargs     = self.scope["url_route"]["kwargs"]
        session_id = kwargs.get("session_id")
        share_code = kwargs.get("share_code")

        session = await self._resolve_session(session_id, share_code)
        if not session:
            await self.close(code=4004)
            return

        self.session    = session
        self.group_name = session_group(session.pk)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send full current state to the newly-connected guardian
        state = await database_sync_to_async(self._build_initial_state)()
        await self.send(json.dumps({"type": "initial_state", **state}))

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """Guardians can acknowledge danger events."""
        try:
            data = json.loads(text_data)
        except Exception:
            return

        if data.get("type") == "acknowledge_danger":
            await self._acknowledge_danger(data.get("event_id"))

    async def broadcast_message(self, event):
        """Receive from group and forward to this guardian's WebSocket."""
        await self.send(json.dumps(event["payload"]))

    # ── DB helpers ────────────────────────────────────────────────────────────
    @database_sync_to_async
    def _resolve_session(self, session_id, share_code):
        try:
            if session_id:
                return LiveWatchSession.objects.get(pk=session_id)
            if share_code:
                return LiveWatchSession.objects.get(share_code=share_code.upper())
        except LiveWatchSession.DoesNotExist:
            return None

    def _build_initial_state(self):
        recent_points = list(
            self.session.gps_points.order_by("-recorded_at")[:100]
        )[::-1]
        checkpoints = list(self.session.checkpoints.all())
        open_dangers = list(
            self.session.danger_events.filter(resolved=False)
        )
        return {
            "session":     session_summary(self.session),
            "trail":       [gps_point_to_dict(p) for p in recent_points],
            "checkpoints": [checkpoint_to_dict(c) for c in checkpoints],
            "dangers":     [danger_event_to_dict(e) for e in open_dangers],
        }

    @database_sync_to_async
    def _acknowledge_danger(self, event_id):
        if not event_id:
            return
        user = self.scope["user"]
        if not user.is_authenticated:
            return
        try:
            event = DangerEvent.objects.get(pk=event_id, session=self.session)
            event.acknowledge(user)
        except DangerEvent.DoesNotExist:
            pass
