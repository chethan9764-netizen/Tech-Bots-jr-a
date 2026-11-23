import importlib.util
import os
import sys
import folium
import streamlit as st
from streamlit_folium import st_folium


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COORDINATOR_PATH = os.path.join(BASE_DIR, "coordinator", "coordinator.py")
ROUTE_AGENT_DIR = os.path.join(BASE_DIR, "route_agent")
NOTIFIER_DIR = os.path.join(BASE_DIR, "notifier")


def load_coordinator():
    """Dynamically load coordinate_emergency from coordinator/coordinator.py."""
    coordinator_dir = os.path.dirname(COORDINATOR_PATH)
    if coordinator_dir not in sys.path:
        sys.path.insert(0, coordinator_dir)

    spec = importlib.util.spec_from_file_location("coordinator_mod", COORDINATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.coordinate_emergency


def load_dispatch_locator():
    """Dynamically load find_nearest_dispatch_targets from route_agent/dispatch_locator.py."""
    if ROUTE_AGENT_DIR not in sys.path:
        sys.path.insert(0, ROUTE_AGENT_DIR)

    locator_path = os.path.join(ROUTE_AGENT_DIR, "dispatch_locator.py")
    if not os.path.exists(locator_path):
        return None

    spec = importlib.util.spec_from_file_location("dispatch_locator_mod", locator_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "find_nearest_dispatch_targets", None)


def load_driver_notifier():
    """Dynamically load send_driver_signal from notifier/driver_alert.py."""
    if NOTIFIER_DIR not in sys.path:
        sys.path.insert(0, NOTIFIER_DIR)

    notifier_path = os.path.join(NOTIFIER_DIR, "driver_alert.py")
    if not os.path.exists(notifier_path):
        return None

    spec = importlib.util.spec_from_file_location("driver_alert_mod", notifier_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "send_driver_signal", None)


st.set_page_config(
    page_title="AmbuPath – Emergency Dispatch Dashboard",
    page_icon="🚑",
    layout="wide",
)

if "dispatch_history" not in st.session_state:
    st.session_state["dispatch_history"] = []

st.title("🚑 AmbuPath – Multi-Agent Emergency Dispatch Dashboard")
st.caption("Powered by Emergency Intelligence Agent, Route Agent, Traffic Agent & Central Coordinator")

# --- SIDEBAR: DISPATCH INPUTS ---
with st.sidebar:
    st.header("🚨 New Emergency Request")

    emergency_id = st.text_input("Emergency ID", value="AMB002")
    description = st.text_area(
        "Emergency Description (for ML Triage)",
        value="Severe road accident near Kavoor junction",
        height=80,
    )
    emergency_location = st.text_input(
        "Emergency / Incident Location",
        value="Kavoor, Mangaluru, Karnataka, India",
    )
    auto_nearest = st.checkbox(
        "Auto-pick Nearest Ambulance & Hospital",
        value=True,
    )

    if auto_nearest:
        start_location = ""
        hospital_location = ""
        st.caption("Nearest ambulance stand and hospital will be selected automatically from the emergency location.")
    else:
        start_location = st.text_input(
            "Ambulance Starting Location",
            value="Kavoor, Mangaluru, Karnataka, India",
        )
        hospital_location = st.text_input(
            "Destination Hospital",
            value="Father Muller Medical College Hospital, Mangaluru, Karnataka, India",
        )

    st.subheader("🚦 Simulated Traffic Conditions")
    route1_traffic = st.selectbox("Route 1 Traffic", ["LOW", "MODERATE", "HIGH", "SEVERE"], index=1)
    route2_traffic = st.selectbox("Route 2 Traffic", ["LOW", "MODERATE", "HIGH", "SEVERE"], index=0)

    st.subheader("📲 Driver Mobile Signal")
    send_mobile_alert = st.checkbox("Send Signal to Driver Mobile", value=True)
    driver_topic = st.text_input(
        "Driver ntfy Topic",
        value="ambupath-mlr-driver-01",
    )

    dispatch_clicked = st.button("🚀 Run Multi-Agent Dispatch", type="primary", width="stretch")

# --- RUN PIPELINE ON BUTTON CLICK ---
if dispatch_clicked:
    st.session_state["dispatch_result"] = None
    st.session_state["dispatch_error"] = None

    with st.spinner("Running Emergency Agent → Route Agent → Traffic Agent..."):
        try:
            nearest_info = None
            resolved_start = start_location.strip()
            resolved_hospital = hospital_location.strip()

            if auto_nearest:
                find_nearest_fn = load_dispatch_locator()
                if find_nearest_fn is None:
                    raise ImportError("Could not find find_nearest_dispatch_targets in route_agent/dispatch_locator.py")
                nearest_info = find_nearest_fn(emergency_location.strip())
                resolved_start = nearest_info["nearest_ambulance"]["query"]
                resolved_hospital = nearest_info["nearest_hospital"]["query"]
            else:
                if not resolved_start:
                    resolved_start = emergency_location.strip()
                if not resolved_hospital:
                    resolved_hospital = "KMC Hospital Attavar, Mangaluru, Karnataka, India"

            coordinate_emergency = load_coordinator()
            request_payload = {
                "emergency_id": emergency_id.strip() or "AMB001",
                "description": description.strip() or "medical emergency",
                "emergency_location": emergency_location.strip(),
                "location": resolved_start,
                "hospital": resolved_hospital,
            }
            simulated_traffic = {
                "Route 1": route1_traffic,
                "Route 2": route2_traffic,
            }

            dispatch_output = coordinate_emergency(
                request_payload,
                simulated_traffic=simulated_traffic,
            )
            dispatch_output["nearest_info"] = nearest_info
            dispatch_output["emergency_location_input"] = emergency_location.strip()

            if send_mobile_alert:
                try:
                    send_signal_fn = load_driver_notifier()
                    if send_signal_fn is None:
                        raise ImportError("Could not find send_driver_signal in notifier/driver_alert.py")
                    dispatch_output["driver_alert_status"] = send_signal_fn(
                        dispatch_output,
                        topic=driver_topic,
                    )
                except Exception as alert_exc:
                    dispatch_output["driver_alert_status"] = {
                        "sent": False,
                        "error": str(alert_exc),
                    }

            st.session_state["dispatch_result"] = dispatch_output

            em_sum = dispatch_output.get("emergency_summary", {})
            act_rt = dispatch_output.get("final_active_route", {})
            st.session_state["dispatch_history"].insert(0, {
                "ID": dispatch_output.get("emergency_id"),
                "Emergency Location": emergency_location.strip(),
                "Category": em_sum.get("category"),
                "Priority": em_sum.get("priority", "HIGH"),
                "Ambulance Start": dispatch_output.get("start_location", "").split(",")[0],
                "Hospital": dispatch_output.get("hospital_location", "").split(",")[0],
                "Active Route": act_rt.get("route_name"),
                "Adj ETA (min)": act_rt.get("adjusted_duration_min"),
                "Traffic": dispatch_output.get("traffic_status"),
            })
        except Exception as exc:
            st.session_state["dispatch_error"] = str(exc)

# --- DISPLAY ERRORS OR RESULTS ---
if st.session_state.get("dispatch_error"):
    st.error(f"Dispatch Error: {st.session_state['dispatch_error']}")

result = st.session_state.get("dispatch_result")

if result:
    emergency_summary = result.get("emergency_summary", {})
    active_route = result.get("final_active_route", {})
    evaluated_routes = result.get("evaluated_routes", [])
    alert = result.get("coordinator_alert")
    nearest_info = result.get("nearest_info")
    driver_alert = result.get("driver_alert_status")

    # Priority & SLA Banner
    priority = emergency_summary.get("priority", "HIGH")
    target_sla = emergency_summary.get("target_response_min", 15)
    adj_eta = active_route.get("adjusted_duration_min", 0)

    banner_text = (
        f"**PRIORITY: {priority}** — Target Response SLA: **{target_sla} mins** | "
        f"Adjusted ETA: **{adj_eta} mins**"
    )
    if priority == "CRITICAL":
        st.error(f"🚨 {banner_text}")
    elif priority == "HIGH":
        st.warning(f"⚠️ {banner_text}")
    else:
        st.info(f"ℹ️ {banner_text}")

    # Traffic Alert Banner
    if alert:
        st.warning(f"⚠️ **COORDINATOR ALERT:** {alert['message']}")
    else:
        st.success("✅ **ROUTE CLEAR:** No severe traffic congestion detected on the active route.")

    # Driver Mobile Signal Status Banner
    if driver_alert:
        if driver_alert.get("sent"):
            st.success(f"📲 Driver mobile signal sent to topic `{driver_alert.get('channel')}`.")
        else:
            st.warning(f"⚠️ Driver mobile signal failed: {driver_alert.get('error')}")

    # Auto-Selected Nearby Dispatch Summary
    if nearest_info:
        near_amb = nearest_info["nearest_ambulance"]
        near_hosp = nearest_info["nearest_hospital"]
        inc = nearest_info["incident"]
        st.info(
            f"📍 **Incident:** {inc['display_name']}  |  "
            f"🚑 **Nearest Ambulance:** {near_amb['name']} (~{near_amb['eta_min']} min drive, {near_amb['straight_km']} km straight-line)  |  "
            f"🏥 **Nearest Hospital:** {near_hosp['name']} (~{near_hosp['eta_min']} min drive, {near_hosp['straight_km']} km straight-line)"
        )

    # Top Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Predicted Category (Agent 1)",
            value=str(emergency_summary.get("category", "N/A")).replace("_", " ").title(),
            delta=f"{float(emergency_summary.get('confidence', 0)):.1f}% confidence",
        )
    with col2:
        st.metric(
            label="Active Route",
            value=active_route.get("route_name", "Route 1"),
            delta="Rerouted" if result.get("reroute_needed") else "Primary Route",
        )
    with col3:
        st.metric(
            label="Distance",
            value=f"{active_route.get('distance_km', 0)} km",
        )
    with col4:
        base_eta = active_route.get("base_duration_min", 0)
        delay = round(adj_eta - base_eta, 2)
        st.metric(
            label="Traffic-Adjusted ETA",
            value=f"{adj_eta} min",
            delta=f"+{delay} min delay" if delay > 0 else "On schedule",
            delta_color="inverse",
        )

    st.divider()

    # Map & Multi-Agent Breakdown
    map_col, details_col = st.columns([3, 2])

    with map_col:
        st.subheader("🗺️ Live Multi-Route Comparison Map")
        start_coords = result.get("start_coordinates", {})
        dest_coords = result.get("destination_coordinates", {})
        active_name = active_route.get("route_name")

        if start_coords and dest_coords:
            center_lat = (start_coords["latitude"] + dest_coords["latitude"]) / 2
            center_lon = (start_coords["longitude"] + dest_coords["longitude"]) / 2
            route_map = folium.Map(location=[center_lat, center_lon], zoom_start=12)

            if nearest_info and nearest_info.get("incident"):
                inc_pt = nearest_info["incident"]
                folium.Marker(
                    [inc_pt["latitude"], inc_pt["longitude"]],
                    popup=f"Emergency Location: {inc_pt['display_name']}",
                    tooltip="Emergency / Incident Location",
                    icon=folium.Icon(color="orange", icon="exclamation-triangle", prefix="fa"),
                ).add_to(route_map)

            folium.Marker(
                [start_coords["latitude"], start_coords["longitude"]],
                popup=f"Ambulance Start: {result.get('start_location')}",
                tooltip="Ambulance Starting Point",
                icon=folium.Icon(color="red", icon="ambulance", prefix="fa"),
            ).add_to(route_map)

            folium.Marker(
                [dest_coords["latitude"], dest_coords["longitude"]],
                popup=f"Hospital: {result.get('hospital_location')}",
                tooltip="Destination Hospital",
                icon=folium.Icon(color="green", icon="hospital-o", prefix="fa"),
            ).add_to(route_map)

            # Alternative routes drawn as dashed lines
            for rt in evaluated_routes:
                coords = rt.get("coordinates", [])
                rt_name = rt.get("route_name", "Route")
                if coords and rt_name != active_name:
                    alt_path = [[pt[1], pt[0]] for pt in coords]
                    folium.PolyLine(
                        alt_path,
                        color="#6c757d",
                        weight=4,
                        opacity=0.7,
                        dash_array="8",
                        tooltip=(
                            f"{rt_name} (Alternative) — "
                            f"{rt.get('traffic_level', 'N/A')} | "
                            f"ETA: {rt.get('adjusted_duration_min', 'N/A')} min"
                        ),
                    ).add_to(route_map)

            # Active route drawn boldly on top
            active_coords = active_route.get("coordinates", [])
            if active_coords:
                active_path = [[pt[1], pt[0]] for pt in active_coords]
                active_color = "#e67e22" if result.get("traffic_status") == "CONGESTION_ALERT" else "#1f77b4"
                folium.PolyLine(
                    active_path,
                    color=active_color,
                    weight=7,
                    opacity=0.92,
                    tooltip=(
                        f"{active_name} (ACTIVE) — "
                        f"{active_route.get('traffic_level', 'N/A')} | "
                        f"ETA: {active_route.get('adjusted_duration_min', 'N/A')} min"
                    ),
                ).add_to(route_map)

            st_folium(route_map, width=None, height=450, returned_objects=[])
        else:
            st.info("Route coordinates unavailable for map rendering.")

    with details_col:
        st.subheader("🤖 Multi-Agent Breakdown")

        st.markdown("**1. Emergency Intelligence Agent**")
        st.json(emergency_summary)

        st.markdown("**2. Route & Traffic Comparison**")
        if evaluated_routes:
            table_rows = []
            for rt in evaluated_routes:
                rt_name = rt.get("route_name")
                table_rows.append({
                    "Route": f"⭐ {rt_name}" if rt_name == active_name else rt_name,
                    "Dist (km)": rt.get("distance_km"),
                    "Base (min)": rt.get("base_duration_min"),
                    "Adj ETA (min)": rt.get("adjusted_duration_min"),
                    "Traffic": rt.get("traffic_level"),
                    "Score": rt.get("congestion_score"),
                })
            st.dataframe(table_rows, width="stretch")

        if result.get("coordinator_logs"):
            st.markdown("**3. Coordinator Logs**")
            for log in result["coordinator_logs"]:
                st.info(log)
else:
    st.info("👈 Enter an emergency location and description in the sidebar, then click **Run Multi-Agent Dispatch**.")

# --- SESSION DISPATCH HISTORY ---
if st.session_state.get("dispatch_history"):
    st.divider()
    st.subheader("📋 Session Dispatch History")
    st.dataframe(st.session_state["dispatch_history"], width="stretch")