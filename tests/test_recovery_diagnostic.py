from src.posture.recovery import RecoveryDetector
from src.perception.posture_features import PostureAngles
from scripts.diagnose_recovery import reason


def test_diagnostic_distinguishes_frame_age_confidence_and_bad_posture():
    detector = RecoveryDetector()
    sample = PostureAngles(1, 0, 0, 1)
    confirmation = detector.update(sample, 2.5)
    assert reason(sample, 2.5, None, detector, confirmation, "good") == "stale_frame"
    sample = PostureAngles(2, 0, 0, 0.2)
    confirmation = detector.update(sample, 2.5)
    assert reason(sample, 2.5, 1, detector, confirmation, "good") == "low_confidence"
    sample = PostureAngles(3, 30, 0, 1)
    confirmation = detector.update(sample, 3.5)
    assert reason(sample, 3.5, 2, detector, confirmation, "slouch") == "raw_slouch"


def test_diagnostic_distinguishes_waiting_and_confirmation():
    detector = RecoveryDetector()
    sample = PostureAngles(1, 0, 0, 1)
    confirmation = detector.update(sample, 1.5)
    assert reason(sample, 1.5, None, detector, confirmation, "good") == "waiting_good_frames_or_span"
    sample = PostureAngles(1.5, 0, 0, 1)
    confirmation = detector.update(sample, 2)
    assert reason(sample, 2, 1, detector, confirmation, "good") == "confirmed"
