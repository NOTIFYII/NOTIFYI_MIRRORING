"""현재 자세 반응 로그 테스트. 하드웨어 없이 돈다."""

import json

from src.telemetry.event_log import EventLogger
from src.telemetry.response_tracker import ResponseTracker


class TestResponseTracker:
    def test_good_after_deadline_is_not_success(self, tmp_path):
        logger = EventLogger(tmp_path)
        tracker = ResponseTracker(logger, response_timeout_sec=5)
        tracker.intervention(0, "forward_head", "mirror")
        tracker.update(6, "good")
        rows = [json.loads(line) for line in logger.path.read_text().splitlines()]
        assert rows[-1]["event"] == "intervention_ignored"

    def test_gap_censors_response_and_does_not_extend_maintenance(self, tmp_path):
        logger = EventLogger(tmp_path)
        tracker = ResponseTracker(logger)
        tracker.intervention(0, "forward_head", "mirror")
        tracker.update(1, "unknown", observation_reason="robot_moving")
        tracker.update(3, "good")
        tracker.update(4, "unknown", observation_reason="robot_moving")
        tracker.update(10, "slouch")
        rows = [json.loads(line) for line in logger.path.read_text().splitlines()]
        corrected = next(r for r in rows if r["event"] == "posture_corrected")
        maintained = next(r for r in rows if r["event"] == "posture_maintenance")
        assert corrected["unobserved_sec"] == 2
        assert not corrected["observation_complete"]
        assert maintained["good_duration_sec"] == 1
        assert not maintained["observation_complete"]

    def test_records_response_and_maintenance(self, tmp_path):
        logger = EventLogger(tmp_path, condition="posture_trigger", session_id="responded")
        tracker = ResponseTracker(logger, response_timeout_sec=15.0)
        base = logger.started_at

        tracker.intervention(base + 1.0, "slouch", "mirror")
        tracker.update(base + 4.5, "good")
        tracker.update(base + 12.0, "slouch")
        logger.close(base + 13.0)

        rows = [json.loads(line) for line in logger.path.read_text().splitlines()]
        events = [row["event"] for row in rows]
        assert events == [
            "session_started", "intervention", "posture_corrected",
            "posture_maintenance", "session_finished",
        ]
        corrected = rows[2]
        assert corrected["response_time_sec"] == 3.5
        assert rows[3]["good_duration_sec"] == 7.5

    def test_timeout_records_ignored_intervention(self, tmp_path):
        logger = EventLogger(tmp_path, condition="posture_trigger", session_id="ignored")
        tracker = ResponseTracker(logger, response_timeout_sec=5.0)
        base = logger.started_at

        tracker.intervention(base + 1.0, "forward_head", "voice")
        tracker.update(base + 6.1, "forward_head")
        logger.close(base + 7.0)

        rows = [json.loads(line) for line in logger.path.read_text().splitlines()]
        assert rows[2]["event"] == "intervention_ignored"
        assert rows[2]["reason"] == "timeout"
