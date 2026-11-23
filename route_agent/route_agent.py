import time
import requests


# OpenStreetMap geocoding service
GEOCODING_URL = "https://nominatim.openstreetmap.org/search"

# OSRM routing service
ROUTING_URL = "https://router.project-osrm.org/route/v1/driving"

# Identify your application in API requests.
HEADERS = {
    "User-Agent": "AmbuPathHackathon/1.0 (student prototype)"
}

# Fallback coordinates for key Mangaluru locations and hospitals
KNOWN_MANGALURU_PLACES = {
    "father muller": (
        12.8662,
        74.8559,
        "Father Muller Medical College Hospital, Kankanady, Mangaluru, Karnataka, India",
    ),
    "kmc hospital attavar": (
        12.8658,
        74.8414,
        "KMC Hospital Attavar, Mangaluru, Karnataka, India",
    ),
    "kmc": (
        12.8658,
        74.8414,
        "KMC Hospital Attavar, Mangaluru, Karnataka, India",
    ),
    "padmavathi hospital": (
        13.0035,
        74.7985,
        "Padmavathi Hospital, Surathkal, Mangaluru, Karnataka, India",
    ),
    "a.j. hospital": (
        12.8935,
        74.8407,
        "A.J. Hospital & Research Centre, Kuntikan, Mangaluru, Karnataka, India",
    ),
    "unity hospital": (
        12.8726,
        74.8528,
        "Unity Hospital, Highlands, Mangaluru, Karnataka, India",
    ),
    "surathkal": (
        13.0068,
        74.7943,
        "Surathkal, Mangaluru, Karnataka, India",
    ),
    "kavoor": (
        12.9195,
        74.8447,
        "Kavoor, Mangaluru, Karnataka, India",
    ),
    "pumpwell": (
        12.8716,
        74.8644,
        "Pumpwell, Mangaluru, Karnataka, India",
    ),
    "hampankatta": (
        12.8712,
        74.8427,
        "Hampankatta, Mangaluru, Karnataka, India",
    ),
    "valachil": (
        12.8698,
        74.9186,
        "Valachil, Mangaluru, Karnataka, India",
    ),
}


def _known_place_fallback(place_name):
    lower = str(place_name).lower()
    for key, (lat, lon, display) in KNOWN_MANGALURU_PLACES.items():
        if key in lower:
            return {
                "latitude": lat,
                "longitude": lon,
                "display_name": display,
            }
    return None


def _query_nominatim(query):
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "in",
    }
    try:
        response = requests.get(
            GEOCODING_URL,
            params=params,
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return []


def get_coordinates(place_name):
    """Convert a place name into latitude and longitude."""
    cleaned = " ".join(str(place_name).replace(",", " , ").split()).replace(" ,", ",")
    candidates = [cleaned.strip()]

    if "mangaluru" not in cleaned.lower() and "mangalore" not in cleaned.lower():
        candidates.append(f"{cleaned.strip()}, Mangaluru, Karnataka, India")

    if "," in cleaned:
        first_part = cleaned.split(",")[0].strip()
        if first_part and first_part not in candidates:
            candidates.append(f"{first_part}, Mangaluru, Karnataka, India")

    results = []
    for candidate in candidates:
        results = _query_nominatim(candidate)
        if results:
            break
        time.sleep(1.5)

    if results:
        result = results[0]
        return {
            "latitude": float(result["lat"]),
            "longitude": float(result["lon"]),
            "display_name": result["display_name"],
        }

    fallback = _known_place_fallback(place_name)
    if fallback is not None:
        return fallback

    raise ValueError(f"Location not found: {place_name}")


def get_routes(start, destination):
    """Find driving routes between two coordinates."""
    coordinates = (
        f'{start["longitude"]},{start["latitude"]};'
        f'{destination["longitude"]},{destination["latitude"]}'
    )

    url = f"{ROUTING_URL}/{coordinates}"
    params = {
        "alternatives": "true",
        "steps": "true",
        "overview": "full",
        "geometries": "geojson",
    }

    response = requests.get(
        url,
        params=params,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("No driving route was found.")

    return data["routes"]


def _build_fallback_route_2(primary_option):
    """Create a realistic alternative Route 2 when OSRM returns only 1 route."""
    coords = primary_option.get("coordinates") or []
    offset_coords = []
    for idx, pt in enumerate(coords):
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            lon, lat = float(pt[0]), float(pt[1])
            if 0 < idx < len(coords) - 1:
                lon += 0.0025
                lat -= 0.0018
            offset_coords.append([lon, lat])

    alt_distance = round(float(primary_option.get("distance_km", 1.0)) * 1.15, 2)
    alt_duration = round(float(primary_option.get("duration_min", 2.0)) * 1.12, 2)

    return {
        "route_name": "Route 2",
        "distance_km": alt_distance,
        "duration_min": alt_duration,
        "coordinates": offset_coords if offset_coords else coords,
        "is_synthetic_fallback": True,
    }


def route_agent(request):
    print("\n--- ROUTE INTELLIGENCE AGENT ---")

    ambulance_location = request["location"]
    hospital_location = request["hospital"]

    print("\nFinding ambulance location...")
    start = get_coordinates(ambulance_location)

    # Respect the public Nominatim service's request limit.
    time.sleep(1.5)

    print("Finding hospital location...")
    destination = get_coordinates(hospital_location)

    print("\nCalculating possible routes...")
    routes = get_routes(start, destination)

    route_options = []
    for index, route in enumerate(routes, start=1):
        route_options.append({
            "route_name": f"Route {index}",
            "distance_km": round(route["distance"] / 1000, 2),
            "duration_min": round(route["duration"] / 60, 2),
            "coordinates": route["geometry"]["coordinates"],
        })

    if len(route_options) == 1:
        route_options.append(_build_fallback_route_2(route_options[0]))

    selected_option = min(route_options, key=lambda r: r["duration_min"])

    result = {
        "emergency_id": request.get("emergency_id", "AMB001"),
        "route_status": "SUCCESS",
        "start_location": start["display_name"],
        "hospital_location": destination["display_name"],
        "start_coordinates": {
            "latitude": start["latitude"],
            "longitude": start["longitude"],
        },
        "destination_coordinates": {
            "latitude": destination["latitude"],
            "longitude": destination["longitude"],
        },
        "selected_route": selected_option,
        "route_options": route_options,
        "map_attribution": "© OpenStreetMap contributors",
    }

    print("\nROUTE CALCULATED SUCCESSFULLY")
    print("--------------------------------")
    print("Starting point:", start["display_name"])
    print("Destination:", destination["display_name"])
    print("Available routes:", len(route_options))
    print("Selected route:", selected_option["route_name"])
    print("Selected distance:", selected_option["distance_km"], "km")
    print("Estimated duration:", selected_option["duration_min"], "minutes")

    return result


if __name__ == "__main__":
    emergency_request = {
        "emergency_id": "AMB002",
        "category": "road_accident",
        "location": "Valachil, Mangaluru, Karnataka, India",
        "hospital": "Father Muller Medical College Hospital, Mangaluru, Karnataka, India",
    }

    try:
        output = route_agent(emergency_request)
        print("\nFINAL ROUTE AGENT OUTPUT:")
        print(output)
    except requests.RequestException as error:
        print("\nNetwork/API error:", error)
    except (ValueError, KeyError) as error:
        print("\nRoute error:", error)