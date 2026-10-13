"""현재 자세 반응 로그 테스트. 하드웨어 없이 돈다."""

import json

from src.telemetry.event_log import EventLogger
from src.telemetry.response_tracker import ResponseTracker


class TestResponseTracker:
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
