import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.benchmark_pi_runtime import CASES, apply_affinity, percentile, summarize


def test_summary_retains_low_fps_timing_even_when_no_person_detected():
    row = summarize([{"inference_ms": 500, "frame_age_ms": 520, "angles": None},
                     {"inference_ms": 600, "frame_age_ms": 620, "angles": None}], 1.1)
    assert row["frames"] == 2
    assert row["inference_p50_ms"] == 550
    assert row["fps"] == 1.82
    assert not row["quality_sample_sufficient"]
    assert row["posture_detection_rate"] == 0
    assert row["torso_sd"] is None


def test_summary_reports_quality_separately_from_speed():
    samples = [{"inference_ms": 460, "frame_age_ms": 497, "angles": [10, 20]}] * 10
    row = summarize(samples, 5)
    assert row["quality_sample_sufficient"]
    assert row["posture_detection_rate"] == 1
    assert row["torso_sd"] == 0
    assert "angles" not in row


def test_affinity_uses_allowed_cores_not_assumed_core_numbers():
    with patch("scripts.benchmark_pi_runtime.os.sched_getaffinity", create=True,
               side_effect=[{2, 3, 6, 7}, {2, 3}]), \
            patch("scripts.benchmark_pi_runtime.os.sched_setaffinity", create=True) as set_affinity:
        assert apply_affinity(2) == [2, 3]
        set_affinity.assert_called_once_with(0, [2, 3])


def test_unavailable_core_count_rejected_before_importing_model():
    with patch("scripts.benchmark_pi_runtime.os.sched_getaffinity", create=True, return_value={3}):
        with pytest.raises(RuntimeError):
            apply_affinity(2)


def test_baseline_has_no_cpu_or_opencv_override():
    assert CASES["baseline"] == {"opencv_threads": None, "cores": None, "input_width": None}
    assert percentile([], 0.5) is None


def test_benchmark_never_imports_robot_control():
    path = Path(__file__).resolve().parents[1] / "scripts/benchmark_pi_runtime.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(module.startswith(("src.robot", "src.main")) for module in imported)
