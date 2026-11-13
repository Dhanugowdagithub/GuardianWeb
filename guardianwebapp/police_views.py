from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import EmergencyAlert
from .police import ESCALATION_SECONDS, nearest_station


def _nobody_responded(alert):
    return (not alert.resolved
            and alert.accepted_by_id is None
            and alert.accepted_by_guardian_id is None
            and alert.status != "Accepted")


@login_required
def sos_status(request, alert_id):
    alert = get_object_or_404(EmergencyAlert, id=alert_id, user=request.user)

    if not _nobody_responded(alert):
        return JsonResponse({"state": "handled"})

    age = (timezone.now() - alert.created_at).total_seconds()
    if age >= ESCALATION_SECONDS:
        return JsonResponse({"state": "police",
                             "url": reverse("police_connected", args=[alert.id])})

    return JsonResponse({"state": "waiting",
                         "seconds_left": int(ESCALATION_SECONDS - age)})


@login_required
def police_connected(request, alert_id):
    alert = get_object_or_404(EmergencyAlert, id=alert_id, user=request.user)

    if not _nobody_responded(alert):
        return redirect("notifications_view")

    age = (timezone.now() - alert.created_at).total_seconds()
    if age < ESCALATION_SECONDS:
        return redirect("notifications_view")

    station, dist = nearest_station(alert.latitude, alert.longitude)
    eta = max(3, round(dist / 30 * 60))

    return render(request, "guardianwebapp/police_connected.html", {
        "alert": alert,
        "station": station,
        "distance_km": round(dist, 1),
        "eta_min": eta,
        "ref": f"GW-{alert.created_at:%Y%m%d}-{alert.id:04d}",
        "map_url": (f"https://www.openstreetmap.org/?mlat={alert.latitude}"
                    f"&mlon={alert.longitude}#map=16/{alert.latitude}/{alert.longitude}"),
    })