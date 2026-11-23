import os
import joblib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "emergency_model.pkl")

model = joblib.load(MODEL_PATH)

PRIORITY_MAP = {
    "cardiac_arrest": ("CRITICAL", 8),
    "heart_attack": ("CRITICAL", 8),
    "stroke": ("CRITICAL", 10),
    "road_accident": ("CRITICAL", 10),
    "trauma": ("HIGH", 12),
    "fire": ("HIGH", 12),
    "breathing_difficulty": ("HIGH", 10),
    "burn": ("HIGH", 15),
    "fracture": ("MODERATE", 20),
    "fever": ("MODERATE", 25),
}


def get_priority_details(category):
    normalized = str(category).strip().lower().replace(" ", "_")
    if normalized in PRIORITY_MAP:
        return PRIORITY_MAP[normalized]

    if any(k in normalized for k in ("cardiac", "heart", "stroke", "accident", "unconscious")):
        return "CRITICAL", 10
    if any(k in normalized for k in ("trauma", "fire", "bleed", "burn", "breath")):
        return "HIGH", 12
    return "MODERATE", 20


def emergency_agent(request):
    print("\n--- EMERGENCY INTELLIGENCE AGENT ---")

    description = request.get("description") or request.get("category", "medical emergency")
    prediction = model.predict([description])[0]
    probabilities = model.predict_proba([description])[0]
    confidence = max(probabilities) * 100

    priority, target_response_min = get_priority_details(prediction)

    return {
        "emergency_id": request.get("emergency_id", "AMB001"),
        "category": prediction,
        "priority": priority,
        "target_response_min": target_response_min,
        "emergency_location": request.get("emergency_location") or request.get("location", "Surathkal, Mangaluru, Karnataka, India"),
        "location": request.get("location", "Surathkal, Mangaluru, Karnataka, India"),
        "hospital": request.get("hospital", "KMC Hospital Attavar, Mangaluru, Karnataka, India"),
        "confidence": round(float(confidence), 2),
    }