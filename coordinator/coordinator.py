import importlib.util
import os
import sys


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _import_module_from_path(module_name, relative_path):
    """Dynamically load a module from a relative path under AmbuPath / hackathon aiml."""
    file_path = os.path.join(BASE_DIR, relative_path)
    if not os.path.exists(file_path):
        return None

    module_dir = os.path.dirname(file_path)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_emergency_agent(request):
    """Run Agent 1 (ml_model/emergency_agent.py) if available, with safe fallback."""
    print("\n--- COORDINATOR: STEP 1 (EMERGENCY AGENT) ---")
    mod = _import_module_from_path("emergency_agent_mod", os.path.join("ml_model", "emergency_agent.py"))

    if mod is not None:
        for fn_name in ("emergency_agent", "predict_emergency", "classify_emergency", "run_agent"):
            fn = getattr(mod, fn_name, None)
            if callable(fn):
                try:
                    output = fn(request)
                    if isinstance(output, dict):
                        return output
                    return {"prediction": output}
                except Exception as exc:
                    print(f"[WARN] {fn_name} raised {exc}; using fallback triage.")
                    break

    category = request.get("category", "general_emergency")
    high_priority_categories = {"road_accident", "cardiac_arrest", "stroke", "trauma", "fire"}
    severity = "HIGH" if str(category).lower() in high_priority_categories else "MODERATE"
    return {
        "emergency_id": request.get("emergency_id", "AMB001"),
        "category": category,
        "severity": severity,
        "source": "coordinator_fallback",
    }


def run_route_agent(request):
    """Run Agent 2 (route_agent/route_agent.py)."""
    print("\n--- COORDINATOR: STEP 2 (ROUTE AGENT) ---")
    mod = _import_module_from_path("route_agent_mod", os.path.join("route_agent", "route_agent.py"))
    if mod is None or not hasattr(mod, "route_agent"):
        raise ImportError("Could not find route_agent in route_agent/route_agent.py")
    return mod.route_agent(request)


def run_traffic_agent(route_output, simulated_traffic=None):
    """Run Agent 3 (traffic_agent/traffic_agent.py)."""
    print("\n--- COORDINATOR: STEP 3 (TRAFFIC AGENT) ---")
    mod = _import_module_from_path("traffic_agent_mod", os.path.join("traffic_agent", "traffic_agent.py"))
    if mod is None or not hasattr(mod, "traffic_agent"):
        raise ImportError("Could not find traffic_agent in traffic_agent/traffic_agent.py")
    return mod.traffic_agent(route_output, simulated_traffic=simulated_traffic)


def coordinate_emergency(request, simulated_traffic=None):
    """
    Orchestrate Agent 1 -> Agent 2 -> Agent 3 and return a unified dispatch payload.
    """
    print("\n==========================================")
    print("       AMBUPATH CENTRAL COORDINATOR")
    print("==========================================")

    emergency_id = request.get("emergency_id", "AMB001")

    # 1. Emergency Triage (Agent 1)
    emergency_result = run_emergency_agent(request)

    # 2. Initial Route Calculation (Agent 2)
    route_result = run_route_agent(request)

    # 3. Traffic Evaluation & Reroute Check (Agent 3)
    traffic_result = run_traffic_agent(route_result, simulated_traffic=simulated_traffic)

    coordinator_logs = []
    alert = traffic_result.get("coordinator_alert")
    if alert:
        coordinator_logs.append(alert["message"])
        print("\n[COORDINATOR ALERT RECEIVED]:", alert["message"])

    if traffic_result.get("request_new_route_from_agent2"):
        log_msg = (
            f"Coordinator noted request_new_route_from_agent2=True for {emergency_id}; "
            f"retaining active route '{traffic_result['active_route']['route_name']}'."
        )
        coordinator_logs.append(log_msg)
        print("[COORDINATOR ACTION]:", log_msg)

    active_route = traffic_result["active_route"]

    final_dispatch = {
        "emergency_id": emergency_id,
        "status": "DISPATCH_READY",
        "emergency_summary": emergency_result,
        "start_location": route_result.get("start_location"),
        "hospital_location": route_result.get("hospital_location"),
        "start_coordinates": route_result.get("start_coordinates"),
        "destination_coordinates": route_result.get("destination_coordinates"),
        "initial_selected_route": route_result.get("selected_route"),
        "traffic_status": traffic_result.get("traffic_status"),
        "reroute_needed": traffic_result.get("reroute_needed"),
        "coordinator_alert": alert,
        "coordinator_logs": coordinator_logs,
        "final_active_route": active_route,
        "evaluated_routes": traffic_result.get("evaluated_routes", []),
        "map_attribution": route_result.get("map_attribution", "© OpenStreetMap contributors"),
    }

    print("\n--- FINAL COORDINATOR DISPATCH SUMMARY ---")
    print("Emergency ID:", final_dispatch["emergency_id"])
    print("Emergency Summary:", emergency_result)
    print("Category:", emergency_result.get("category"))
    print("Priority:", emergency_result.get("priority", "HIGH"))
    print("Target Response (min):", emergency_result.get("target_response_min", 15))
    print("From:", final_dispatch["start_location"])
    print("To:", final_dispatch["hospital_location"])
    print("Traffic Status:", final_dispatch["traffic_status"])
    print("Reroute Needed:", final_dispatch["reroute_needed"])
    print("Active Route:", active_route["route_name"])
    print("Distance (km):", active_route["distance_km"])
    print("Base ETA (min):", active_route["base_duration_min"])
    print("Adjusted ETA (min):", active_route["adjusted_duration_min"])

    return final_dispatch


if __name__ == "__main__":
    sample_emergency = {
        "emergency_id": "AMB002",
        "category": "road_accident",
        "description": "Severe road accident near Surathkal highway",
        "location": "Surathkal, Mangaluru, Karnataka, India",
        "hospital": "KMC Hospital Attavar, Mangaluru, Karnataka, India",
    }

    dispatch_output = coordinate_emergency(
        sample_emergency,
        simulated_traffic={"Route 1": "HIGH", "Route 2": "LOW"},
    )

    print("\nFINAL COORDINATOR PAYLOAD:")
    print(dispatch_output)