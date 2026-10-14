#!/usr/bin/env python3
"""원시 회복 확인 조건을 프레임별로 출력한다. 모터/설정은 변경하지 않는다."""
import argparse
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def reason(sample, now, previous_timestamp, detector, confirmation, raw_label):
    if not all(math.isfinite(value) for value in (sample.timestamp, sample.confidence,
                                                  sample.torso_pitch_deg, sample.neck_pitch_deg, sample.lateral_tilt_deg)):
        return "invalid_values"
    if previous_timestamp is not None and sample.timestamp <= previous_timestamp:
        return "duplicate_or_old_frame"
    if not 0 <= now - sample.timestamp <= detector.max_age:
        return "stale_frame"
    if sample.confidence < detector.confidence:
        return "low_confidence"
    if raw_label != "good":
        return f"raw_{raw_label}"
    if confirmation.confirmed:
        return "confirmed"
    if previous_timestamp is not None and sample.timestamp - previous_timestamp > detector.max_gap:
        return "frame_gap_reset"
    return "waiting_good_frames_or_span"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera")
    parser.add_argument("--seconds", type=float, default=30)
    args = parser.parse_args()
    if not 5 <= args.seconds <= 120:
        parser.error("seconds는 5~120초여야 합니다")
    import yaml
    from src.camera.camera_stream import CameraStream
    from src.perception.pose_estimator import PoseEstimator
    from src.perception.posture_features import PostureAngles, extract_angles
    from src.posture.classifier import classify
    from src.posture.recovery import RecoveryDetector
    from src.runtime.instance import instance_lock

    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "config/posture.yaml").read_text(encoding="utf-8"))
    p = config["perception"]
    recovery = config["recovery"]
    detector = RecoveryDetector(**{key: value for key, value in recovery.items() if key != "enabled"})
    previous = None
    print("모터는 조작하지 않습니다. 모델 준비 후 나쁜 자세→정상 자세를 유지하세요.", flush=True)
    with instance_lock(), CameraStream(args.camera or p["camera"], p["width"], p["height"], True) as camera, \
            PoseEstimator(p["model"]) as estimator:
        started = time.monotonic()
        while time.monotonic() - started < args.seconds:
            frame = camera.read()
            if frame is None:
                continue
            captured = camera.last_captured_at
            landmarks, world = estimator.detect(frame, max(0, (captured - started) * 1000))
            sample = None
            if landmarks and world:
                sample = extract_angles(world, landmarks, captured, p["min_visibility"],
                                        p["invert_torso"], p["invert_neck"])
            sample = sample or PostureAngles(captured, 0, 0, 0)
            now = time.monotonic()
            label = classify(sample).label
            confirmation = detector.update(sample, now)
            gap = (captured - previous) * 1000 if previous is not None else None
            print(f"[RECOVERY] raw={label} conf={sample.confidence:.3f} "
                  f"age_ms={(now-captured)*1000:.1f} gap_ms={gap} "
                  f"good_frames={len(detector.frames)} confirmed={confirmation.confirmed} "
                  f"reason={reason(sample, now, previous, detector, confirmation, label)}", flush=True)
            previous = captured
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError) as exc:
        sys.exit(str(exc))
