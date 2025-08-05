GUEST_PURPOSE_CATEGORIES = {
    "meeting": ["meeting", "meet", "interview", "appointment", "discussion"],
    "event": ["event", "seminar", "orientation", "activity", "conference"],
    "delivery": ["delivery", "drop", "courier", "package", "shipment"],
    "tour": ["tour", "visit", "observation", "campus tour", "walk-in"],
    "security": ["security", "check", "inspection", "id validation", "verification"],
    "other": []
}

def classify_guest_purpose(text):
    text = (text or "").lower()
    for category, keywords in GUEST_PURPOSE_CATEGORIES.items():
        for keyword in keywords:
            if keyword in text:
                return category
    return "other"
