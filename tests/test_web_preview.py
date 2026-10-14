import time
from urllib.error import HTTPError
from urllib.request import urlopen

import numpy as np
import pytest

from src.camera.web_preview import WebPreview


def test_loopback_page_stream_and_shutdown():
    with WebPreview(port=0) as preview:
        assert preview._server.server_address[0] == "127.0.0.1"
        url = f"http://127.0.0.1:{preview.port}"
        with urlopen(url, timeout=2) as response:
            assert b"read-only" in response.read()
        with pytest.raises(HTTPError) as error:
            urlopen(url + "/motor/move", timeout=2)
        assert error.value.code == 404
        preview.submit(np.zeros((480, 640, 3), dtype=np.uint8))
        with urlopen(url + "/stream.mjpg", timeout=2) as response:
            assert "multipart" in response.headers["Content-Type"]
            assert response.readline() == b"--frame\r\n"
            assert response.readline() == b"Content-Type: image/jpeg\r\n"
            size = int(response.readline().split(b":")[1])
            assert response.readline() == b"\r\n"
            assert response.read(size).startswith(b"\xff\xd8")
    assert not preview._encoder.is_alive()
    assert not preview._http_thread.is_alive()


def test_throttling_and_encoder_failure_do_not_block(monkeypatch):
    import cv2
    monkeypatch.setattr(cv2, "imencode", lambda *_: (_ for _ in ()).throw(ValueError()))
    with WebPreview(port=0) as preview:
        preview.submit(np.zeros((2, 2, 3), dtype=np.uint8))
        assert not preview.ready()
        time.sleep(0.15)
        assert preview._encoder.is_alive()
        assert preview._jpeg is None


@pytest.mark.parametrize("fps", [0, -1, 6, float("nan")])
def test_invalid_fps(fps):
    with pytest.raises(ValueError):
        WebPreview(fps=fps)
