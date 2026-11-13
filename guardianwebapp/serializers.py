"""
livewatch/serializers.py
Lightweight dict helpers used by consumers + REST views.
No DRF dependency required.
"""


def gps_point_to_dict(point):
    return {
        "id":          point.pk,
        "lat":         point.latitude,
        "lng":         point.longitude,
        "accuracy":    point.accuracy,
        "altitude":    point.altitude,
        "speed":       point.speed,
        "heading":     point.heading,
        "recorded_at": point.recorded_at.isoformat(),
    }


def checkpoint_to_dict(cp):
    return {
        "id":           cp.pk,
        "name":         cp.name,
        "lat":          cp.latitude,
        "lng":          cp.longitude,
        "radius_m":     cp.radius_m,
        "order":        cp.order,
        "confirmed":    cp.confirmed,
        "confirmed_at": cp.confirmed_at.isoformat() if cp.confirmed_at else None,
        "confirmed_how": cp.confirmed_how,
    }


def danger_event_to_dict(event):
    return {
        "id":           event.pk,
        "trigger":      event.trigger,
        "level":        event.level,
        "description":  event.description,
        "lat":          event.latitude,
        "lng":          event.longitude,
        "acknowledged": event.acknowledged,
        "resolved":     event.resolved,
        "created_at":   event.created_at.isoformat(),
    }


def session_summary(session):
    return {
        "id":               session.pk,
        "title":            session.title,
        "status":           session.status,
        "share_code":       session.share_code,
        "origin_name":      session.origin_name,
        "destination_name": session.destination_name,
        "origin_lat":       session.origin_lat,
        "origin_lng":       session.origin_lng,
        "destination_lat":  session.destination_lat,
        "destination_lng":  session.destination_lng,
        "started_at":       session.started_at.isoformat(),
        "expected_duration": session.expected_duration,
        "is_overdue":       session.is_overdue,
        "sos_triggered":    session.sos_triggered,
    }
