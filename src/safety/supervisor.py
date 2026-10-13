"""제어 지령이 하드웨어에 나가기 전 마지막 관문.

관절 한계는 JointMapper 가 이미 자르지만, 여기서는 시간축을 본다.
한 주기에 얼마나 크게 움직여도 되는지, 사람이 사라졌을 때 무엇을 할지.
"""

from dataclasses import dataclass

TICKS_PER_DEG = 4096 / 360.0

STATE_TRACKING = "tracking"
STATE_RETURNING = "returning"
STATE_IDLE = "idle"
STATE_SAFE_STOP = "safe_stop"
STATE_PERSON_LOST = "person_lost_hold"


@dataclass
class SlewLimiter:
    """제어 주기당 관절 변화량을 제한한다.

    인식이 튀면 목표가 순간적으로 크게 바뀔 수 있다. 그대로 내보내면
    관절이 튀어 아래 단에 충격이 간다.
    """

    max_step_ticks: float

    def apply(self, current, targets):
        if self.max_step_ticks <= 0:
            raise ValueError("max_step_ticks 는 0 보다 커야 합니다")
        limited = {}
        for name, target in targets.items():
            if name not in current:
                limited[name] = target
                continue
            delta = target - current[name]
            if delta > self.max_step_ticks:
                delta = self.max_step_ticks
            elif delta < -self.max_step_ticks:
                delta = -self.max_step_ticks
            limited[name] = int(round(current[name] + delta))
        return limited


def max_step_ticks(max_step_deg):
    return max_step_deg * TICKS_PER_DEG


class IdlePolicy:
    """사람 감지 손실 시 마지막 목표를 유지하는 상태 기계.

    tracking -> (짧은 누락은 유예) -> person_lost_hold
    사람 미감지만으로 중립 이동이나 토크 해제를 시작하지 않는다.
    """

    def __init__(self, return_seconds, release_seconds, tolerance_ticks=15,
                 grace_seconds=0.5, distance_fn=None):
        self.return_seconds = return_seconds
        self.release_seconds = release_seconds
        self.tolerance_ticks = tolerance_ticks
        # 인식은 몇 프레임씩 끊긴다. 그때마다 중립으로 출발했다 돌아오면
        # 로봇이 덜컥거린다. 이 시간만큼 연속으로 안 보이면 hold 상태를 표시한다.
        self.grace_seconds = grace_seconds
        self.distance_fn = distance_fn or (lambda name, current, target:
                                           target - current)
        self.state = STATE_TRACKING
        self._missing_since = None

    def update(self, now, person_visible, current, neutral):
        """상태를 갱신하고 (state, 토크 유지 여부) 를 반환한다.

        current와 neutral 인자는 기존 호출부와의 호환을 위해 받지만,
        사람 감지 손실 시에는 위치나 zero 여부에 따라 목표를 바꾸지 않는다.
        """
        if person_visible:
            self.state = STATE_TRACKING
            self._missing_since = None
            return STATE_TRACKING, True

        if self._missing_since is None:
            self._missing_since = now
        if now - self._missing_since >= self.grace_seconds:
            self.state = STATE_PERSON_LOST

        # Torque stays enabled so gravity cannot collapse the structure.
        # The control loop must keep its last commanded target until reacquired.
        return self.state, True
