"""Experimental side-view features for validation ONLY; not a posture classifier."""
import math
from src.perception.posture_features import (
    LEFT_EAR, RIGHT_EAR, LEFT_SHOULDER, RIGHT_SHOULDER, point_visible,
)


def side_candidate(landmarks, width, height, threshold=0.5):
    base = {"control_enabled": False, "method": "ear_shoulder_image_vector_v1"}
    if not landmarks:
        return dict(base, available=False, reason="no_landmarks")
    pairs = [("left", LEFT_EAR, LEFT_SHOULDER),
             ("right", RIGHT_EAR, RIGHT_SHOULDER)]
    candidates = []
    for side, ear_index, shoulder_index in pairs:
        ear, shoulder = landmarks[ear_index], landmarks[shoulder_index]
        if not all(point_visible(p, threshold) for p in (ear, shoulder)):
            continue
        dx = (ear.x - shoulder.x) * width
        dy = (shoulder.y - ear.y) * height
        if math.hypot(dx, dy) < 20:
            continue
        candidates.append(dict(side=side, confidence=min(ear.visibility, shoulder.visibility),
                               image_vector_deg=round(math.degrees(math.atan2(dx, dy)), 3)))
    if not candidates:
        return dict(base, available=False, reason="ear_shoulder_unavailable")
    return dict(base, available=True, **max(candidates, key=lambda c: c["confidence"]))
