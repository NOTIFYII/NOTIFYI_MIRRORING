"""같은 계정의 Notifyi 실행이 카메라/버스를 중복 점유하지 않도록 한다."""
import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


class AlreadyRunning(RuntimeError):
    pass


@contextmanager
def instance_lock(path=None):
    path = path or Path(tempfile.gettempdir()) / f"notifyi-{os.getuid()}.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if os.fstat(fd).st_uid != os.getuid():
            raise AlreadyRunning("실행 잠금 파일 소유자가 다릅니다")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AlreadyRunning("Notifyi가 이미 실행 중입니다. 기존 실행/자동 서비스를 먼저 종료하세요")
        yield
    finally:
        os.close(fd)

