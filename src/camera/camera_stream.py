"""카메라 캡처. 열기 실패와 프레임 유실을 여기서 흡수한다."""

import platform
import threading
import time
import warnings

import cv2

# 플랫폼별 캡처 백엔드. Linux 는 V4L2 가 안정적이고,
# macOS 는 AVFoundation, Windows 는 DSHOW 를 쓴다.
_BACKENDS = {
    "Linux": cv2.CAP_V4L2,
    "Darwin": cv2.CAP_AVFOUNDATION,
    "Windows": cv2.CAP_DSHOW,
}
_DEFAULT_BACKEND = _BACKENDS.get(platform.system(), cv2.CAP_ANY)


class CameraError(RuntimeError):
    pass


class CameraStream:
    """source 는 인덱스(0) 또는 /dev/videoN 형식을 받는다.

    OpenCV 의 Linux V4L2 백엔드는 장치 경로 문자열 대신 정수 인덱스를
    요구하므로 /dev/videoN 을 N 으로 변환한다.
    """

    def __init__(self, source=0, width=640, height=480, latest_only=True):
        self.source = source
        self.width = width
        self.height = height
        self._capture = None
        self.latest_only = latest_only
        self.last_captured_at = None
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._thread = None
        self._frame = None
        self._sequence = 0
        self._consumed_sequence = 0
        self._captured_at = None
        self._error = None

    def __enter__(self):
        if self._thread is not None and self._thread.is_alive():
            raise CameraError("이전 카메라 읽기가 아직 종료되지 않았습니다")
        self._thread = None
        source = self.source
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        elif (isinstance(source, str) and source.startswith("/dev/video")
              and source.removeprefix("/dev/video").isdigit()):
            source = int(source.removeprefix("/dev/video"))
        self._capture = cv2.VideoCapture(source, _DEFAULT_BACKEND)
        if not self._capture.isOpened():
            self._capture.release()
            raise CameraError(
                f"카메라 {self.source} 를 열 수 없습니다. "
                "다른 프로그램이 쓰고 있는지, 장치가 있는지 확인하세요.")
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._stop.clear()
        self._frame = None
        self._sequence = self._consumed_sequence = 0
        self._error = None
        if self.latest_only:
            self._thread = threading.Thread(target=self._capture_latest,
                                            name="camera-latest", daemon=True)
            self._thread.start()
        return self

    def _capture_latest(self):
        """카메라 스레드만 read/release를 수행하고 최신 프레임 하나를 보관한다."""
        capture = self._capture
        try:
            while not self._stop.is_set():
                ok, frame = capture.read()
                captured_at = time.monotonic()
                if not ok or frame is None:
                    self._stop.wait(0.02)
                    continue
                with self._condition:
                    self._frame = frame
                    self._captured_at = captured_at
                    self._sequence += 1
                    self._condition.notify_all()
        except Exception as exc:
            with self._condition:
                self._error = str(exc)
                self._condition.notify_all()
        finally:
            capture.release()

    def __exit__(self, *exc):
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            if self._thread.is_alive():
                message = "카메라 읽기가 종료되지 않았습니다. 재실행 전 장치/프로세스를 확인하세요."
                warnings.warn(message)
                # blocked read와 release를 동시에 호출하지 않는다.
                if not exc or exc[0] is None:
                    raise CameraError(message)
                return False
        elif self._capture is not None:
            self._capture.release()
        self._capture = None
        return False

    def read(self):
        """BGR 프레임. 읽지 못하면 None."""
        if self._capture is None:
            raise CameraError("카메라가 열려 있지 않습니다")
        if self.latest_only:
            with self._condition:
                self._condition.wait_for(lambda: self._sequence > self._consumed_sequence
                                         or self._error is not None or self._stop.is_set(),
                                         timeout=0.5)
                if self._error is not None:
                    raise CameraError(f"카메라 읽기 실패: {self._error}")
                if self._stop.is_set() or self._sequence <= self._consumed_sequence:
                    return None
                frame = self._frame
                self.last_captured_at = self._captured_at
                self._consumed_sequence = self._sequence
        else:
            ok, frame = self._capture.read()
            self.last_captured_at = time.monotonic()
            if not ok or frame is None:
                return None
        # 거울처럼 보이는 편이 자세를 확인하기 쉽다.
        return cv2.flip(frame, 1)
