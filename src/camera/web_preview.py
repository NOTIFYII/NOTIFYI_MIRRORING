"""Loopback-only, read-only MJPEG preview. Never opens a camera or motor bus."""

import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class WebPreview:
    def __init__(self, port=8765, fps=2.0):
        if not 0 <= port <= 65535 or not 0 < fps <= 5:
            raise ValueError("웹 프리뷰 port=0~65535, fps=0 초과~5 이하")
        self.port = port
        self.period = 1 / fps
        self._next = 0.0
        self._frames = queue.Queue(maxsize=1)
        self._condition = threading.Condition()
        self._jpeg = None
        self._sequence = 0
        self._stop = threading.Event()
        self._clients = threading.BoundedSemaphore(4)

    def __enter__(self):
        preview = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == "/":
                    body = (b'<!doctype html><meta name="viewport" content="width=device-width">'
                            b'<title>Notifyi preview</title><body style="background:#111;color:white">'
                            b'<h2>Notifyi - read-only live preview</h2>'
                            b'<p>No motor controls. Close this page to disconnect.</p>'
                            b'<img src="/stream.mjpg" style="max-width:100%">')
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path != "/stream.mjpg":
                    self.send_error(404)
                    return
                if not preview._clients.acquire(blocking=False):
                    self.send_error(503)
                    return
                try:
                    self.connection.settimeout(2.0)
                    self.send_response(200)
                    self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    sequence = -1
                    while not preview._stop.is_set():
                        with preview._condition:
                            preview._condition.wait_for(
                                lambda: preview._stop.is_set() or
                                (preview._jpeg is not None and preview._sequence != sequence),
                                timeout=1.0)
                            if preview._stop.is_set():
                                break
                            if preview._jpeg is None or preview._sequence == sequence:
                                continue
                            jpeg, sequence = preview._jpeg, preview._sequence
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                         + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                        self.wfile.flush()
                except (OSError, TimeoutError):
                    pass
                finally:
                    preview._clients.release()

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.port = self._server.server_port
        self._http_thread = threading.Thread(
            target=lambda: self._server.serve_forever(poll_interval=0.1), daemon=True)
        self._encoder = threading.Thread(target=self._encode, daemon=True)
        self._http_thread.start()
        self._encoder.start()
        return self

    def ready(self):
        return not self._stop.is_set() and time.monotonic() >= self._next

    def submit(self, frame):
        now = time.monotonic()
        if self._stop.is_set() or now < self._next:
            return
        self._next = now + self.period
        try:
            self._frames.put_nowait(frame.copy())
        except queue.Full:
            pass  # Slow encoder drops frames instead of blocking inference.

    def _encode(self):
        import cv2
        while not self._stop.is_set():
            try:
                frame = self._frames.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                height, width = frame.shape[:2]
                if width > 480:
                    frame = cv2.resize(frame, (480, max(1, round(height * 480 / width))))
                ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                if ok:
                    with self._condition:
                        self._jpeg = jpeg.tobytes()
                        self._sequence += 1
                        self._condition.notify_all()
            except Exception:
                continue  # Preview failure must not interrupt motor control.

    def __exit__(self, *_):
        self._stop.set()
        with self._condition:
            self._condition.notify_all()
        self._server.shutdown()
        self._server.server_close()
        self._http_thread.join(timeout=1)
        self._encoder.join(timeout=1)
