import math

ESCALATION_SECONDS = 60

STATIONS = [
    {"name": "Station A Police Station", "area": "Area A",
     "phone": "080-0000-0001", "lat": 12.9716, "lng": 77.5946},
    {"name": "Station B Police Station", "area": "Area B",
     "phone": "080-0000-0002", "lat": 12.9352, "lng": 77.6245},
    {"name": "Station C Police Station", "area": "Area C",
     "phone": "080-0000-0003", "lat": 13.0358, "lng": 77.5970},
]

def distance_km(lat1, lng1, lat2, lng2):
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

def nearest_station(lat, lng):
    best = min(STATIONS, key=lambda s: distance_km(lat, lng, s["lat"], s["lng"]))
    return best, distance_km(lat, lng, best["lat"], best["lng"])