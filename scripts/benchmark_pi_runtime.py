#!/usr/bin/env python3
"""Pi 인식 성능 비교. 모터/토크에 접근하지 않고 설정을 자동 변경하지 않는다."""
import argparse
import json
import math
import os
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MARKER = "NOTIFYI_BENCH_RESULT="
CASES = {
    "baseline": {"opencv_threads": None, "cores": None, "input_width": None},
    "opencv1": {"opencv_threads": 1, "cores": None, "input_width": None},
    "cores2": {"opencv_threads": 1, "cores": 2, "input_width": None},
    "resize480": {"opencv_threads": 1, "cores": None, "input_width": 480},
    "resize320": {"opencv_threads": 1, "cores": None, "input_width": 320},
}


def hardware_status():
    result = {"machine": platform.machine(), "python": platform.python_version()}
    for key, args in (("temperature", ["vcgencmd", "measure_temp"]),
                      ("throttled", ["vcgencmd", "get_throttled"]),
                      ("arm_clock", ["vcgencmd", "measure_clock", "arm"])):
        try:
            completed = subprocess.run(args, capture_output=True, text=True, timeout=3)
            result[key] = completed.stdout.strip() if completed.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            result[key] = None
    return result


def apply_affinity(cores):
    if not hasattr(os, "sched_getaffinity"):
        if cores is not None:
            raise RuntimeError("CPU 코어 제한은 Linux에서만 측정할 수 있습니다")
        return None
    available = sorted(os.sched_getaffinity(0))
    if cores is not None:
        if len(available) < cores:
            raise RuntimeError(f"사용 가능한 CPU가 {len(available)}개라 {cores}개 시험을 할 수 없습니다")
        # cv2/MediaPipe import 전에 적용하여 생성되는 native 스레드도 제한한다.
        os.sched_setaffinity(0, available[:cores])
    return sorted(os.sched_getaffinity(0))


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    if fraction == 0.5:
        return round(statistics.median(ordered), 1)
    return round(ordered[max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))], 1)


def summarize(samples, elapsed):
    valid = [sample for sample in samples if sample["angles"] is not None]
    return {
        "frames": len(samples), "valid_postures": len(valid),
        "measured_seconds": round(elapsed, 3),
        "fps": round(len(samples) / elapsed, 2) if elapsed else 0,
        "posture_detection_rate": round(len(valid) / len(samples), 3) if samples else 0,
        "inference_p50_ms": percentile([s["inference_ms"] for s in samples], 0.5),
        "inference_p95_ms": percentile([s["inference_ms"] for s in samples], 0.95),
        "frame_age_p50_ms": percentile([s["frame_age_ms"] for s in samples], 0.5),
        "torso_sd": round(statistics.pstdev(s["angles"][0] for s in valid), 2) if len(valid) > 1 else None,
        "neck_sd": round(statistics.pstdev(s["angles"][1] for s in valid), 2) if len(valid) > 1 else None,
        "quality_sample_sufficient": len(valid) >= 10,
    }


def worker(case_name, seconds, warmup, camera_source):
    case = CASES[case_name]
    affinity = apply_affinity(case["cores"])
    import cv2
    import yaml
    from src.camera.camera_stream import CameraStream
    from src.perception.pose_estimator import PoseEstimator
    from src.perception.posture_features import extract_angles

    if case["opencv_threads"] is not None:
        cv2.setNumThreads(case["opencv_threads"])
    config = yaml.safe_load((ROOT / "config/posture.yaml").read_text(encoding="utf-8"))
    perception = config["perception"]
    before = hardware_status()
    setup_started = time.monotonic()
    samples = []
    # 모든 시험은 같은 원본 카메라 해상도/화각. 추론 입력만 종횡비 유지 축소.
    with CameraStream(camera_source or perception["camera"], perception["width"],
                      perception["height"], True) as camera, PoseEstimator("lite") as estimator:
        setup_seconds = time.monotonic() - setup_started
        origin = time.monotonic()
        measurement_started = None
        warmed_frames = 0
        deadline = origin + warmup + seconds + 20
        measured_shape = None
        while time.monotonic() < deadline:
            if measurement_started is not None and time.monotonic() - measurement_started >= seconds:
                break
            frame = camera.read()
            if frame is None:
                continue
            captured_at = camera.last_captured_at
            if case["input_width"] and frame.shape[1] > case["input_width"]:
                width = case["input_width"]
                height = round(frame.shape[0] * width / frame.shape[1])
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            measured_shape = list(frame.shape[:2])
            mark = time.monotonic()
            landmarks, world = estimator.detect(frame, max(0, (captured_at - origin) * 1000))
            finished = time.monotonic()
            angles = None
            if landmarks and world:
                posture = extract_angles(world, landmarks, captured_at, perception["min_visibility"],
                                         perception["invert_torso"], perception["invert_neck"])
                if posture is not None:
                    angles = [posture.torso_pitch_deg, posture.neck_pitch_deg]
            if measurement_started is None:
                warmed_frames += 1
                if finished - origin >= warmup and warmed_frames >= 3:
                    measurement_started = finished
                continue
            samples.append({"inference_ms": (finished - mark) * 1000,
                            "frame_age_ms": (finished - captured_at) * 1000, "angles": angles})
        elapsed = time.monotonic() - measurement_started if measurement_started is not None else 0
    if not samples:
        raise RuntimeError("카메라/추론 측정 표본이 없습니다")
    return {"case": case_name, "opencv_threads": cv2.getNumThreads(), "cpu_affinity": affinity,
            "input_height_width": measured_shape, "setup_seconds": round(setup_seconds, 2),
            "before": before, "after": hardware_status(), **summarize(samples, elapsed)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=12)
    parser.add_argument("--warmup", type=float, default=3)
    parser.add_argument("--camera")
    parser.add_argument("--cases", nargs="+", choices=list(CASES), default=list(CASES))
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", choices=list(CASES), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 5 <= args.seconds <= 120 or not 0 <= args.warmup <= 30 or not 1 <= args.repeat <= 3:
        parser.error("seconds 5~120, warmup 0~30, repeat 1~3 범위를 사용하세요")
    if args.worker:
        print(MARKER + json.dumps(worker(args.worker, args.seconds, args.warmup, args.camera)))
        return 0
    from src.runtime.instance import instance_lock
    output = args.output or ROOT / "data/runtime_benchmarks" / f"{time.time_ns()}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    # 카메라/모델 실행 전에 출력 충돌과 현재 앱 실행을 확인한다.
    with instance_lock(), output.open("x", encoding="utf-8") as stream:
        results = []
        print("모터는 조작하지 않습니다. 같은 자리에서 정상 자세를 유지하세요.", flush=True)
        # 끝에 baseline을 다시 측정해 발열/시간 경과에 따른 편향을 확인한다.
        sequence = [(name, repeat) for repeat in range(args.repeat) for name in args.cases]
        if "baseline" in args.cases:
            sequence.append(("baseline", args.repeat))
        for index, (name, repeat) in enumerate(sequence, 1):
            print(f"[{index}/{len(sequence)}] {name} · 모델 준비 후 {args.seconds:g}초 측정", flush=True)
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", name,
                       "--seconds", str(args.seconds), "--warmup", str(args.warmup)]
            if args.camera:
                command.extend(["--camera", args.camera])
            try:
                completed = subprocess.run(command, capture_output=True, text=True,
                                           timeout=args.seconds + args.warmup + 120)
                lines = [line[len(MARKER):] for line in completed.stdout.splitlines() if line.startswith(MARKER)]
                if completed.returncode or not lines:
                    raise RuntimeError(f"종료코드 {completed.returncode}: {completed.stderr[-1200:]}")
                row = json.loads(lines[-1])
            except (subprocess.TimeoutExpired, RuntimeError, ValueError) as exc:
                row = {"case": name, "error": str(exc)}
            row["repeat"] = repeat
            results.append(row)
            stream.seek(0)
            json.dump({"source": "read_only_pi_runtime_benchmark", "results": results,
                       "changes_applied": False}, stream, ensure_ascii=False, indent=2)
            stream.truncate()
            stream.flush()
            print(f"  {row.get('fps', '?')} fps | 추론 {row.get('inference_p50_ms', '?')}ms | 검출 {row.get('posture_detection_rate', '?')} | 오류 {row.get('error', '없음')}", flush=True)
        print(f"저장: {output}. YAML/모터 설정은 변경하지 않았습니다.")
        return 1 if any("error" in row for row in results) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError) as exc:
        sys.exit(str(exc))
