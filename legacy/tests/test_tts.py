from legacy.src.audio.tts import SpeechQueue


class TestSpeechQueue:
    def test_disabled_queue_is_a_noop(self):
        speaker = SpeechQueue({"enabled": False})
        assert speaker.submit("안내") is False

    def test_duplicate_text_is_suppressed_during_cooldown(self):
        speaker = SpeechQueue({
            "enabled": True,
            "command": ["fake-tts"],
            "cooldown_sec": 8.0,
        })
        assert speaker.submit("안내", now=10.0) is True
        assert speaker.submit("안내", now=15.0) is False
        assert speaker.submit("안내", now=19.0) is True
