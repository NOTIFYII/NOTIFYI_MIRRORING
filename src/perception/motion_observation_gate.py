"""Exclude captures during commanded/encoder movement and subsequent settling."""
import math
import threading


class MotionObservationGate:
    def __init__(self, distance_fn, settle_sec=0.5, target_tolerance_ticks=15,
                 movement_tolerance_ticks=3, max_measurement_age_sec=0.5):
        values = (settle_sec, target_tolerance_ticks, movement_tolerance_ticks,
                  max_measurement_age_sec)
        if not all(math.isfinite(v) and v > 0 for v in values):
            raise ValueError("motion observation limits must be finite and positive")
        self.distance = distance_fn
        self.settle_sec = settle_sec
        self.target_tolerance = target_tolerance_ticks
        self.movement_tolerance = movement_tolerance_ticks
        self.max_age = max_measurement_age_sec
        self._lock = threading.Lock()
        self._targets = None
        self._positions = None
        self._measured_at = None
        self._quiet_since = None
        self._ready_since = None
        self._reason = "robot_starting"

    def update(self, now, targets, positions, measured_at):
        with self._lock:
            fresh = (positions is not None and measured_at is not None
                     and 0 <= now - measured_at <= self.max_age
                     and set(positions) == set(targets)
                     and all(math.isfinite(v) for v in positions.values()))
            changed = self._targets != targets
            arrived = fresh and all(abs(self.distance(n, positions[n], t))
                                    <= self.target_tolerance for n, t in targets.items())
            moved = False
            if fresh and self._positions is not None and measured_at != self._measured_at:
                moved = any(abs(self.distance(n, self._positions[n], positions[n]))
                            > self.movement_tolerance for n in targets)
            self._targets = dict(targets)
            if fresh:
                self._positions = dict(positions)
                self._measured_at = measured_at
            if changed or moved or not arrived:
                self._quiet_since = None
                self._ready_since = None
                self._reason = "robot_moving" if fresh else "motor_observation_stale"
            else:
                if self._quiet_since is None:
                    self._quiet_since = now
                if now - self._quiet_since >= self.settle_sec:
                    if self._ready_since is None:
                        self._ready_since = now
                    self._reason = "ready"
                else:
                    self._reason = "robot_settling"

    def reason(self, captured_at, now):
        with self._lock:
            if self._measured_at is None or not 0 <= now - self._measured_at <= self.max_age:
                return "motor_observation_stale"
            if self._ready_since is None:
                return self._reason
            if captured_at < self._ready_since:
                return "capture_before_stable"
            return "ready"
