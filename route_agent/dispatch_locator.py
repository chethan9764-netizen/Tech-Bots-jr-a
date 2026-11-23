import math
import requests

GEOCODING_URL = "https://nominatim.openstreetmap.org/search"
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving"
HEADERS = {"User-Agent": "AmbuPathHackathon/1.0 (student prototype)"}

# Mangaluru ambulance dispatch stands
AMBULANCE_STANDS = [
    {"name": "Surathkal Ambulance Stand", "query": "Surathkal, Mangaluru, Karnataka, India", "lat": 13.0068, "lon": 74.7943},
    {"name": "Kavoor Ambulance Stand", "query": "Kavoor, Mangaluru, Karnataka, India", "lat": 12.9195, "lon": 74.8447},
    {"name": "Pumpwell Ambulance Stand", "query": "Pumpwell, Mangaluru, Karnataka, India", "lat": 12.8716, "lon": 74.8644},
    {"name": "Hampankatta Ambulance Stand", "query": "Hampankatta, Mangaluru, Karnataka, India", "lat": 12.8712, "lon": 74.8427},
]

# Mangaluru hospitals with emergency/trauma support
MANGALURU_HOSPITALS = [
    {"name": "Padmavathi Hospital Surathkal", "query": "Padmavathi Hospital, Surathkal, Mangaluru, Karnataka, India", "lat": 13.0035, "lon": 74.7985},
    {"name": "A.J. Hospital & Research Centre", "query": "A.J. Hospital, Kuntikan, Mangaluru, Karnataka, India", "lat": 12.8935, "lon": 74.8407},
    {"name": "Father Muller Medical College Hospital", "query": "Father Muller Medical College Hospital, Mangaluru, Karnataka, India", "lat": 12.8662, "lon": 74.8559},
    {"name": "KMC Hospital Attavar", "query": "KMC Hospital Attavar, Mangaluru, Karnataka, India", "lat": 12.8658, "lon": 74.8414},
    {"name": "Unity Hospital Mangaluru", "query": "Unity Hospital, Highlands, Mangaluru, Karnataka, India", "lat": 12.8726, "lon": 74.8528},
]


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def geocode_emergency_location(place_name):
    params = {"q": place_name, "format": "jsonv2", "limit": 1, "countrycodes": "in"}
    resp = requests.get(GEOCODING_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"Could not find emergency location: {place_name}")
    top = data[0]
    return {
        "latitude": float(top["lat"]),
        "longitude": float(top["lon"]),
        "display_name": top["display_name"],
    }


def _rank_by_osrm_or_distance(origin_lat, origin_lon, candidates):
    # Try OSRM driving duration table first for realistic road travel time
    coords_list = [f"{origin_lon},{origin_lat}"] + [f"{c['lon']},{c['lat']}" for c in candidates]
    url = f"{OSRM_TABLE_URL}/{';'.join(coords_list)}"
    try:
        resp = requests.get(url, params={"sources": "0"}, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        durations = payload.get("durations", [[]])[0][1:]
        if durations and len(durations) == len(candidates):
            ranked = []
            for item, sec in zip(candidates, durations):
                entry = dict(item)
                entry["straight_km"] = _haversine_km(origin_lat, origin_lon, item["lat"], item["lon"])
                entry["eta_min"] = round(float(sec) / 60.0, 2) if sec is not None else 999.0
                ranked.append(entry)
            ranked.sort(key=lambda x: x["eta_min"])
            return ranked
    except Exception:
        pass

    # Fallback to Haversine distance if OSRM table fails
    ranked = []
    for item in candidates:
        entry = dict(item)
        entry["straight_km"] = _haversine_km(origin_lat, origin_lon, item["lat"], item["lon"])
        entry["eta_min"] = round(entry["straight_km"] * 2.2, 2)
        ranked.append(entry)
    ranked.sort(key=lambda x: x["eta_min"])
    return ranked


def find_nearest_dispatch_targets(emergency_location_str):
    incident = geocode_emergency_location(emergency_location_str)
    nearest_ambulances = _rank_by_osrm_or_distance(
        incident["latitude"], incident["longitude"], AMBULANCE_STANDS
    )
    nearest_hospitals = _rank_by_osrm_or_distance(
        incident["latitude"], incident["longitude"], MANGALURU_HOSPITALS
    )
    return {
        "incident": incident,
        "nearest_ambulance": nearest_ambulances[0],
        "nearest_hospital": nearest_hospitals[0],
        "ambulance_candidates": nearest_ambulances,
        "hospital_candidates": nearest_hospitals,
    }