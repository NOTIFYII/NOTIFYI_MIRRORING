"""회복 관측과 복귀 지령의 시각을 기록한다. 물리적 움직임 검증은 아니다."""
import queue
import threading
import uuid


def milliseconds(end, start):
    return round((end - start) * 1000, 1) if end is not None and start is not None and end >= start else None


class RecoveryLatency:
    def __init__(self):
        self._lock = threading.Lock()
        self._events = queue.SimpleQueue()
        self._trial = None
        self._motion_trial = None
        self._perception = None

    def start(self, now):
        with self._lock:
            if self._trial is not None:
                self._emit("recovery_latency_incomplete", now, trial_id=self._trial["id"], reason="superseded")
            self._trial = {"id": uuid.uuid4().hex[:12], "started": now}
            if self._motion_trial is not None:
                self._emit("recovery_motion_incomplete", now, trial_id=self._motion_trial["id"], reason="superseded")
                self._motion_trial = None
            self._emit("recovery_latency_trial", now, trial_id=self._trial["id"])

    def _emit(self, event, now, **fields):
        self._events.put((event, now, fields))

    def observe(self, captured_at, inferred_at, filtered_at, raw_label, filtered_label):
        with self._lock:
            if raw_label == "unknown":
                self._perception = None
            elif raw_label != "good":
                self._perception = {"bad_seen": True}
            elif self._perception is not None and "capture" not in self._perception:
                self._perception.update(capture=captured_at, inference=inferred_at)
            if filtered_label == "good" and self._perception and "capture" in self._perception:
                p = self._perception
                self._emit("perception_recovery_latency", filtered_at,
                           capture_to_inference_ms=milliseconds(p["inference"], p["capture"]),
                           inference_to_filtered_good_ms=milliseconds(filtered_at, p["inference"]),
                           capture_to_filtered_good_ms=milliseconds(filtered_at, p["capture"]))
                self._perception = None
            trial = self._trial
            if trial is None or captured_at < trial["started"] or "request" in trial:
                return
            if filtered_label != "good" and "filtered" in trial:
                trial.pop("filtered", None)
                trial.pop("capture", None)
                trial.pop("inference", None)
            if raw_label != "good" and "filtered" not in trial:
                trial.pop("capture", None)
                trial.pop("inference", None)
            elif raw_label == "good" and "capture" not in trial:
                trial.update(capture=captured_at, inference=inferred_at)
            if filtered_label == "good" and "filtered" not in trial:
                trial["filtered"] = filtered_at

    def return_requested(self, now, baseline=None, neutral=None):
        with self._lock:
            if self._trial is not None and "request" not in self._trial:
                self._trial["request"] = now
                self._trial["baseline"] = dict(baseline) if baseline is not None else None
                self._trial["neutral"] = dict(neutral) if neutral is not None else None
                self._emit("return_requested", now, trial_id=self._trial["id"])

    def command_sent(self, now):
        with self._lock:
            t = self._trial
            if t is None or "request" not in t:
                return
            self._emit("return_command_sent", now, trial_id=t["id"],
                       capture_to_inference_ms=milliseconds(t.get("inference"), t.get("capture")),
                       inference_to_filtered_good_ms=milliseconds(t.get("filtered"), t.get("inference")),
                       filtered_good_to_request_ms=milliseconds(t.get("request"), t.get("filtered")),
                       request_to_command_ms=milliseconds(now, t.get("request")),
                       capture_to_command_ms=milliseconds(now, t.get("capture")),
                       physical_motion_verified=False)
            t["command"] = now
            self._motion_trial = t
            self._trial = None

    def motion_observed(self, now, positions):
        with self._lock:
            t = self._motion_trial
            if t is None or not t.get("baseline") or not t.get("neutral"):
                return
            body = "body_pitch"
            if body not in positions or body not in t["baseline"] or body not in t["neutral"]:
                return
            before = abs(t["baseline"][body] - t["neutral"][body])
            after = abs(positions[body] - t["neutral"][body])
            if before - after >= 12:
                self._emit("return_motion_observed", now, trial_id=t["id"],
                           command_to_encoder_observation_ms=milliseconds(now, t["command"]),
                           capture_to_encoder_observation_ms=milliseconds(now, t.get("capture")),
                           detection_threshold_ticks=12, polling_interval_sec=0.2,
                           physical_start_time_exact=False)
                self._motion_trial = None

    def close(self, now):
        with self._lock:
            if self._trial is not None:
                self._emit("recovery_latency_incomplete", now, trial_id=self._trial["id"], reason="session_finished_before_command")
                self._trial = None
            if self._motion_trial is not None:
                self._emit("recovery_motion_incomplete", now, trial_id=self._motion_trial["id"], reason="no_fresh_body_motion_observed")
                self._motion_trial = None

    def flush(self, logger, print_summary=False):
        while True:
            try:
                event, now, fields = self._events.get_nowait()
            except queue.Empty:
                return
            logger.record(event, timestamp=now, **fields)
            if print_summary and event in ("return_command_sent", "return_motion_observed", "perception_recovery_latency"):
                print(f"[LATENCY] {event} | {fields}", flush=True)
