from math import radians, sin, cos, sqrt, atan2

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def get_nearest_volunteers(lat, lng, limit=3, max_distance_km=15):
    from .models import Volunteer

    candidates = Volunteer.objects.filter(
        is_available=True,
        latitude__isnull=False,
        longitude__isnull=False,
    )

    scored = []
    for v in candidates:
        dist = haversine_km(lat, lng, v.latitude, v.longitude)
        if dist <= max_distance_km:
            scored.append((dist, v))

    scored.sort(key=lambda x: x[0])
    return [v for _, v in scored[:limit]]

def get_nearby_emergency_alerts(lat, lng, radius_km=2):
    from .models import EmergencyAlert

    candidates = EmergencyAlert.objects.filter(status="Sent")

    nearby = []
    for alert in candidates:
        dist = haversine_km(lat, lng, alert.latitude, alert.longitude)
        if dist <= radius_km:
            nearby.append((dist, alert))

    nearby.sort(key=lambda x: x[0])
    return [alert for _, alert in nearby]