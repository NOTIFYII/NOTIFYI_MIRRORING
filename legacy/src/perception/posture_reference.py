from dataclasses import dataclass
from src.perception.posture_features import PostureAngles

@dataclass(frozen=True)
class PostureReference:
    """바른 자세를 기준으로 잡은 값.

    2D 비율 기반에서도 사람과 카메라 위치마다 '바른 자세'의 수치가 다르다.
    캘리브레이션으로 그 값을 재서 빼면 0 = 바른 자세가 된다.
    """
    torso_pitch_deg: float
    neck_pitch_deg: float


def apply_reference(angles, reference):
    if reference is None:
        return angles
    return PostureAngles(
        timestamp=angles.timestamp,
        torso_pitch_deg=angles.torso_pitch_deg - reference.torso_pitch_deg,
        neck_pitch_deg=angles.neck_pitch_deg - reference.neck_pitch_deg,
        confidence=angles.confidence,
        lateral_tilt_deg=angles.lateral_tilt_deg,
        torso_compression=angles.torso_compression,
        neck_compression=angles.neck_compression,
    )
