from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.runtime.instance import instance_lock, AlreadyRunning
from scripts.install_launchers import render
from scripts.launch_robot import command, main


def test_duplicate_instance_rejected_and_lock_released(tmp_path):
    path = tmp_path / "instance.lock"
    with instance_lock(path):
        with pytest.raises(AlreadyRunning):
            with instance_lock(path):
                pass
    with instance_lock(path):
        pass


def test_auto_service_never_moves_and_has_no_restart():
    desktop, unit = render(Path("/home/notifyi/notiFYI/.venv-mp-pi3/bin/python"),
                           Path("/home/notifyi/notiFYI"))
    assert "--move" not in unit
    assert "Restart=no" in unit
    assert "--move" not in desktop.split("[Desktop Action Move]")[0]
    assert "--move" in desktop.split("[Desktop Action Move]")[1]
    args = SimpleNamespace(preview=False, move=False)
    assert "--no-preview" in command(args) and "--move" not in command(args)
    args.move = True
    assert "--move" in command(args)


def test_takeover_failure_never_executes_robot():
    with patch("scripts.launch_robot.subprocess.run", side_effect=OSError("no systemctl")), \
            patch("scripts.launch_robot.os.execv") as execute:
        assert main(["--takeover-service", "--move"]) == 1
        execute.assert_not_called()
