"""영상 대신 캡처 대기·추론·프레임 지연의 유한 구간 요약만 기록한다."""
import statistics


class PerformanceWindow:
    def __init__(self, interval=5.0):
        self.interval = max(1.0, float(interval))
        self.started_at = None
        self.samples = []
        self.count = 0

    def observe(self, now, capture_wait_ms, inference_ms, frame_age_ms):
        if self.started_at is None:
            self.started_at = now
        self.samples.append((capture_wait_ms, inference_ms, frame_age_ms))
        self.count += 1
        elapsed = now - self.started_at
        if elapsed < self.interval:
            # 입력이 빨라도 요약용 표본이 메모리를 무제한 사용하지 않게 한다.
            self.samples = self.samples[-300:]
            return None
        result = {"samples": self.count, "window_sec": round(elapsed, 3),
                  "processed_fps": round(self.count / elapsed, 2)}
        for index, name in enumerate(("capture_wait_ms", "inference_ms", "frame_age_ms")):
            result[name] = round(statistics.median(sample[index] for sample in self.samples), 1)
        self.samples.clear()
        self.count = 0
        self.started_at = now
        return result
