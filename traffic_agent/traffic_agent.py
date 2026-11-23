import os
import random
import sys


def _load_route_agent():
    """Import route_agent from ../route_agent/route_agent.py if available."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    route_agent_dir = os.path.join(base_dir, "route_agent")
    if route_agent_dir not in sys.path:
        sys.path.insert(0, route_agent_dir)
    try:
        from route_agent import route_agent as external_route_agent
        return external_route_agent
    except ImportError:
        return None


def evaluate_route_traffic(route_option, traffic_level=None):
    """Simulate traffic conditions and congestion score for a single route."""
    allowed_levels = ["LOW", "MODERATE", "HIGH", "SEVERE"]

    if traffic_level is None:
        traffic_level = random.choice(allowed_levels)
    else:
        traffic_level = traffic_level.upper()
        if traffic_level not in allowed_levels:
            raise ValueError(f"Invalid traffic level: {traffic_level}")

    multiplier_map = {
        "LOW": 1.05,
        "MODERATE": 1.25,
        "HIGH": 1.55,
        "SEVERE": 1.90,
    }

    congestion_score_map = {
        "LOW": 20,
        "MODERATE": 50,
        "HIGH": 78,
        "SEVERE": 95,
    }

    multiplier = multiplier_map[traffic_level]
    base_duration = route_option["duration_min"]
    adjusted_duration = round(base_duration * multiplier, 2)
    congestion_score = congestion_score_map[traffic_level]
    is_congested = traffic_level in ("HIGH", "SEVERE")

    return {
        "route_name": route_option.get("route_name", "Route"),
        "distance_km": route_option["distance_km"],
        "base_duration_min": base_duration,
        "adjusted_duration_min": adjusted_duration,
        "traffic_level": traffic_level,
        "congestion_score": congestion_score,
        "is_congested": is_congested,
        "coordinates": route_option.get("coordinates", []),
    }


def traffic_agent(route_output, simulated_traffic=None):
    """
    Inspect simulated traffic on the selected route.
    Identifies congestion, sends an alert payload to the coordinator,
    and switches to a better alternative route if available.
    """
    print("\n--- TRAFFIC INTELLIGENCE AGENT ---")

    emergency_id = route_output.get("emergency_id", "AMB001")
    selected = route_output["selected_route"]
    options = route_output.get("route_options", [selected])
    simulated_traffic = simulated_traffic or {}

    evaluated_routes = []
    for idx, opt in enumerate(options, start=1):
        name = opt.get("route_name", f"Route {idx}")
        forced_level = simulated_traffic.get(name)
        evaluated = evaluate_route_traffic(opt, forced_level)
        evaluated["route_name"] = name
        evaluated_routes.append(evaluated)

    current_eval = next(
        (
            r for r in evaluated_routes
            if r["distance_km"] == selected["distance_km"]
            and r["base_duration_min"] == selected["duration_min"]
        ),
        evaluated_routes[0],
    )

    reroute_needed = False
    final_route = current_eval
    coordinator_alert = None

    if current_eval["is_congested"]:
        print(
            f"[ALERT] Congestion on {current_eval['route_name']}: "
            f"{current_eval['traffic_level']} "
            f"(adjusted ETA: {current_eval['adjusted_duration_min']} min)."
        )

        alternatives = [
            r for r in evaluated_routes
            if r["route_name"] != current_eval["route_name"]
        ]

        if alternatives:
            best_alt = min(
                alternatives,
                key=lambda r: (r["congestion_score"], r["adjusted_duration_min"])
            )
            if (
                best_alt["congestion_score"] < current_eval["congestion_score"]
                or best_alt["adjusted_duration_min"] < current_eval["adjusted_duration_min"]
            ):
                reroute_needed = True
                final_route = best_alt

        coordinator_alert = {
            "to": "coordinator",
            "emergency_id": emergency_id,
            "alert_type": "TRAFFIC_CONGESTION",
            "congested_route": current_eval["route_name"],
            "traffic_level": current_eval["traffic_level"],
            "congestion_score": current_eval["congestion_score"],
            "reroute_requested": reroute_needed,
            "recommended_route": final_route["route_name"] if reroute_needed else None,
            "message": (
                f"Congestion ({current_eval['traffic_level']}) on {current_eval['route_name']} "
                f"for {emergency_id}. "
                + (
                    f"Switching to {final_route['route_name']} "
                    f"(~{final_route['adjusted_duration_min']} min)."
                    if reroute_needed
                    else "No faster alternative in current options; requesting another route."
                )
            ),
        }
        print("Coordinator Alert:", coordinator_alert["message"])
    else:
        print(
            f"[CLEAR] {current_eval['route_name']} has {current_eval['traffic_level']} traffic "
            f"(adjusted ETA: {current_eval['adjusted_duration_min']} min)."
        )

    return {
        "emergency_id": emergency_id,
        "traffic_status": "CONGESTION_ALERT" if current_eval["is_congested"] else "NORMAL",
        "reroute_needed": reroute_needed,
        "request_new_route_from_agent2": current_eval["is_congested"] and not reroute_needed,
        "coordinator_alert": coordinator_alert,
        "active_route": {
            "route_name": final_route["route_name"],
            "distance_km": final_route["distance_km"],
            "base_duration_min": final_route["base_duration_min"],
            "adjusted_duration_min": final_route["adjusted_duration_min"],
            "traffic_level": final_route["traffic_level"],
            "coordinates": final_route["coordinates"],
        },
        "evaluated_routes": [
            {k: v for k, v in r.items() if k != "coordinates"}
            for r in evaluated_routes
        ],
    }


if __name__ == "__main__":
    route_fn = _load_route_agent()

    if route_fn is not None:
        sample_request = {
            "emergency_id": "AMB002",
            "category": "road_accident",
            "location": "Surathkal, Mangaluru, Karnataka, India",
            "hospital": "KMC Hospital Attavar, Mangaluru, Karnataka, India",
        }
        route_data = route_fn(sample_request)
    else:
        route_data = {
            "emergency_id": "AMB002",
            "route_status": "SUCCESS",
            "selected_route": {
                "distance_km": 19.5,
                "duration_min": 28.0,
                "coordinates": [[74.79, 13.01], [74.84, 12.87]],
            },
            "route_options": [
                {
                    "route_name": "Route 1",
                    "distance_km": 19.5,
                    "duration_min": 28.0,
                    "coordinates": [[74.79, 13.01], [74.84, 12.87]],
                },
                {
                    "route_name": "Route 2",
                    "distance_km": 21.2,
                    "duration_min": 31.0,
                    "coordinates": [[74.79, 13.01], [74.85, 12.88]],
                },
            ],
        }

    traffic_output = traffic_agent(
        route_data,
        simulated_traffic={"Route 1": "HIGH", "Route 2": "LOW"},
    )

    print("\nFINAL TRAFFIC AGENT OUTPUT:")
    print(traffic_output)