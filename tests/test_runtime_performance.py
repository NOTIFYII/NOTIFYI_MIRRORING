import queue
import threading

import pytest

from src.camera import camera_stream as camera_module
from src.telemetry.performance import PerformanceWindow
from src.main import load_posture_config


class Capture:
    def __init__(self):
        self.frames = queue.Queue()
        self.releases = []
        self.readers = []
    def isOpened(self):
        return True
    def set(self, *args):
        return True
    def read(self):
        self.readers.append(threading.current_thread().name)
        try:
            value = self.frames.get(timeout=0.02)
        except queue.Empty:
            return False, None
        if isinstance(value, Exception):
            raise value
        return True, value
    def release(self):
        self.releases.append(threading.current_thread().name)


def test_capture_discards_old_frames_preserves_timestamp_and_releases_from_reader(monkeypatch):
    capture = Capture()
    monkeypatch.setattr(camera_module.cv2, "VideoCapture", lambda *args: capture)
    monkeypatch.setattr(camera_module.cv2, "flip", lambda frame, axis: frame)
    stream = camera_module.CameraStream()
    with stream:
        for value in (1, 2, 3):
            capture.frames.put(value)
        with stream._condition:
            assert stream._condition.wait_for(lambda: stream._sequence == 3, timeout=1)
        assert stream.read() == 3
        assert stream.last_captured_at is not None
        assert stream.read() is None  # 같은 이미지를 다시 추론하지 않는다.
    assert capture.releases == ["camera-latest"]
    assert set(capture.readers) == {"camera-latest"}


def test_capture_exception_is_reported_and_released(monkeypatch):
    capture = Capture()
    monkeypatch.setattr(camera_module.cv2, "VideoCapture", lambda *args: capture)
    with camera_module.CameraStream() as stream:
        capture.frames.put(RuntimeError("unplugged"))
        with pytest.raises(camera_module.CameraError, match="unplugged"):
            stream.read()
    assert capture.releases == ["camera-latest"]


def test_sync_capture_compatibility(monkeypatch):
    capture = Capture()
    monkeypatch.setattr(camera_module.cv2, "VideoCapture", lambda *args: capture)
    monkeypatch.setattr(camera_module.cv2, "flip", lambda frame, axis: frame)
    capture.frames.put(4)
    with camera_module.CameraStream(latest_only=False) as stream:
        assert stream.read() == 4
        assert stream.last_captured_at is not None
    assert len(capture.releases) == 1


def test_summary_contains_only_timing_not_frame_data():
    window = PerformanceWindow(5)
    assert window.observe(0, 2, 500, 520) is None
    report = window.observe(5, 4, 600, 610)
    assert report["inference_ms"] == 550
    assert report["frame_age_ms"] == 565
    assert "frame" not in report
    assert window.samples == []


def test_three_second_condition_and_two_axis_mapping_remain():
    config = load_posture_config()
    assert config["correction"]["sustain_seconds"] == 3.0
    assert config["correction"]["check_interval_sec"] == 0.1
    assert config["angles"]["median_window"] == 3


