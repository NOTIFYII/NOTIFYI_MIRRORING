"""새 원시 관측에 한해서 연속 정상 회복을 확인한다. 나쁜 자세 정책과 별개다."""
from collections import deque
from dataclasses import dataclass
import math

from src.posture.classifier import classify


@dataclass(frozen=True)
class RecoveryConfirmation:
    timestamp: float
    confirmed: bool
    first_capture_at: float | None = None
    confirmed_at: float | None = None


class RecoveryDetector:
    def __init__(self, min_frames=2, min_span_sec=0.3, max_gap_sec=1.0,
                 max_age_sec=1.0, min_confidence=0.5):
        if (not isinstance(min_frames, int) or min_frames < 2
                or not all(math.isfinite(x) for x in (min_span_sec, max_gap_sec, max_age_sec, min_confidence))
                or not 0 < min_span_sec <= max_gap_sec or max_age_sec <= 0
                or not 0 < min_confidence <= 1):
            raise ValueError("정상 회복 설정의 프레임 수/시간 제한이 유효하지 않습니다")
        self.frames = deque(maxlen=max(64, min_frames))
        self.min_frames = min_frames
        self.min_span = min_span_sec
        self.max_gap = max_gap_sec
        self.max_age = max_age_sec
        self.confidence = min_confidence
        self.last_timestamp = None

    def update(self, sample, now):
        if self.last_timestamp is not None and sample.timestamp <= self.last_timestamp:
            return RecoveryConfirmation(sample.timestamp, False)
        gap = sample.timestamp - self.last_timestamp if self.last_timestamp is not None else 0
        self.last_timestamp = sample.timestamp
        finite = all(math.isfinite(value) for value in (
            sample.timestamp, sample.confidence, sample.torso_pitch_deg,
            sample.neck_pitch_deg, sample.lateral_tilt_deg))
        fresh = finite and 0 <= now - sample.timestamp <= self.max_age
        if not fresh or sample.confidence < self.confidence or classify(sample).label != "good":
            self.frames.clear()
            return RecoveryConfirmation(sample.timestamp, False)
        if gap > self.max_gap:
            self.frames.clear()
        self.frames.append(sample.timestamp)
        first = None
        if len(self.frames) >= self.min_frames:
            for index in range(len(self.frames) - self.min_frames, -1, -1):
                if self.frames[-1] - self.frames[index] >= self.min_span - 1e-9:
                    first = self.frames[index]
                    break
        confirmed = first is not None
        return RecoveryConfirmation(sample.timestamp, confirmed,
                                    first,
                                    now if confirmed else None)
