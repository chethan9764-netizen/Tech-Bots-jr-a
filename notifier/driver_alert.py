import os
import requests


def _pick_less_traffic_route(dispatch_result: dict) -> dict:
    """Pick the active/least-congested route from dispatch_result."""
    active = dispatch_result.get("final_active_route") or {}
    evaluated = dispatch_result.get("evaluated_routes") or []

    if evaluated:
        best = min(
            evaluated,
            key=lambda r: (
                r.get("congestion_score", 999),
                r.get("adjusted_duration_min", 999),
            ),
        )
        return best

    return active


def send_driver_signal(dispatch_result: dict, topic: str | None = None) -> dict:
    """
    Send an instant mobile notification with:
    - Emergency spot
    - Nearby hospital
    - Less traffic route (with traffic & ETA details)
    """
    channel = (topic or os.getenv("AMBUPATH_DRIVER_TOPIC", "ambupath-mlr-driver-01")).strip()

    emergency = dispatch_result.get("emergency_summary", {})
    best_route = _pick_less_traffic_route(dispatch_result)

    emergency_id = dispatch_result.get("emergency_id", "AMB001")
    priority = str(emergency.get("priority", "HIGH")).upper()
    category = str(emergency.get("category", "emergency")).replace("_", " ").upper()

    emergency_spot = (
        dispatch_result.get("emergency_location_input")
        or emergency.get("emergency_location")
        or dispatch_result.get("start_location")
        or "Not specified"
    )
    nearby_hospital = dispatch_result.get("hospital_location") or emergency.get("hospital") or "Not specified"

    route_name = best_route.get("route_name", "Route 1")
    traffic_level = best_route.get("traffic_level", "LOW/MODERATE")
    eta_min = best_route.get("adjusted_duration_min", best_route.get("duration_min", "N/A"))
    dist_km = best_route.get("distance_km", "N/A")

    title = f"AMBULANCE ALERT [{priority}] - {emergency_id}"
    body = (
        f"Emergency: {category}\n"
        f"📍 Emergency Spot: {emergency_spot}\n"
        f"🏥 Nearby Hospital: {nearby_hospital}\n"
        f"🛣️ Less Traffic Route: {route_name} ({traffic_level} traffic | {dist_km} km | ETA: {eta_min} min)"
    )

    ntfy_priority_map = {
        "CRITICAL": "urgent",
        "HIGH": "high",
        "MODERATE": "default",
    }

    response = requests.post(
        f"https://ntfy.sh/{channel}",
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": ntfy_priority_map.get(priority, "high"),
            "Tags": "ambulance,rotating_light,hospital",
        },
        timeout=10,
    )
    response.raise_for_status()

    return {
        "sent": True,
        "channel": channel,
        "emergency_spot": emergency_spot,
        "nearby_hospital": nearby_hospital,
        "less_traffic_route": route_name,
    }