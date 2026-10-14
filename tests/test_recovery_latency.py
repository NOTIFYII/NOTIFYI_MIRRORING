from src.telemetry.recovery_latency import RecoveryLatency


class Log:
    def __init__(self):
        self.events = []
    def record(self, event, **fields):
        self.events.append((event, fields))


def events(tracker):
    log = Log()
    tracker.flush(log)
    return log.events


def test_stages_are_separate_and_command_is_not_physical_motion():
    tracker = RecoveryLatency()
    tracker.start(1)
    tracker.observe(2, 2.5, 2.51, "good", "slouch")
    tracker.observe(2.6, 3.1, 3.11, "good", "good")
    tracker.return_requested(3.12, {"body_pitch": -340}, {"body_pitch": 1})
    tracker.command_sent(3.14)
    row = dict(events(tracker))["return_command_sent"]
    assert row["capture_to_inference_ms"] == 500
    assert row["inference_to_filtered_good_ms"] == 610
    assert row["filtered_good_to_request_ms"] == 10
    assert row["request_to_command_ms"] == 20
    assert row["capture_to_command_ms"] == 1140
    assert row["physical_motion_verified"] is False
    tracker.motion_observed(3.2, {"body_pitch": -335})
    assert events(tracker) == []
    tracker.motion_observed(3.4, {"body_pitch": -320})
    motion = dict(events(tracker))["return_motion_observed"]
    assert motion["command_to_encoder_observation_ms"] == 260
    assert not motion["physical_start_time_exact"]


def test_dry_run_can_measure_perception_without_robot_events():
    tracker = RecoveryLatency()
    tracker.observe(1, 1.5, 1.51, "slouch", "slouch")
    tracker.observe(2, 2.5, 2.51, "good", "slouch")
    tracker.observe(2.6, 3.1, 3.11, "good", "good")
    rows = events(tracker)
    assert [event for event, _ in rows] == ["perception_recovery_latency"]
    assert rows[0][1]["capture_to_filtered_good_ms"] == 1110


def test_unknown_cannot_count_as_recovery():
    tracker = RecoveryLatency()
    tracker.start(1)
    tracker.observe(2, 2.5, 2.51, "good", "slouch")
    tracker.observe(3, 3.5, 3.51, "unknown", "unknown")
    tracker.observe(4, 4.5, 4.51, "good", "good")
    tracker.return_requested(4.52)
    tracker.command_sent(4.53)
    row = dict(events(tracker))["return_command_sent"]
    assert row["capture_to_command_ms"] == 530


def test_pre_intervention_frames_are_not_recovery():
    tracker = RecoveryLatency()
    tracker.start(3)
    tracker.observe(2, 3.1, 3.11, "good", "good")
    tracker.return_requested(3.12)
    tracker.command_sent(3.13)
    assert dict(events(tracker))["return_command_sent"]["capture_to_command_ms"] is None


def test_failed_command_or_missing_motion_are_incomplete_not_success():
    tracker = RecoveryLatency()
    tracker.start(1)
    tracker.return_requested(2)
    tracker.close(3)
    names = [name for name, _ in events(tracker)]
    assert "recovery_latency_incomplete" in names
    assert "return_command_sent" not in names
    tracker.start(4)
    tracker.return_requested(5)
    tracker.command_sent(6)
    tracker.close(7)
    assert "recovery_motion_incomplete" in [name for name, _ in events(tracker)]


def test_bad_frame_resets_raw_good_candidate():
    tracker = RecoveryLatency()
    tracker.start(1)
    tracker.observe(2, 2.5, 2.51, "good", "slouch")
    tracker.observe(3, 3.5, 3.51, "slouch", "slouch")
    tracker.observe(4, 4.5, 4.51, "good", "good")
    tracker.return_requested(4.52)
    tracker.command_sent(4.53)
    assert dict(events(tracker))["return_command_sent"]["capture_to_command_ms"] == 530
