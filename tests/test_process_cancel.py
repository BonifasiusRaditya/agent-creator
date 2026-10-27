import subprocess
import sys
import threading
import time

from trendforge.media import Cancelled


def test_cancellation_stops_an_actual_running_subprocess(client, tmp_path, monkeypatch):
    worker = client.app.state.worker
    event = threading.Event()
    processes, errors = [], []
    actual_popen = subprocess.Popen

    def record_process(*args, **kwargs):
        process = actual_popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr("trendforge.media.subprocess.Popen", record_process)

    def run():
        try:
            worker.command([sys.executable, "-c",
                "from pathlib import Path; import time; Path('started.txt').touch(); time.sleep(60)"], tmp_path, event, timeout=15)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "started.txt").exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert (tmp_path / "started.txt").exists(), "The test subprocess did not start"
    finally:
        event.set()
        thread.join(timeout=6)
    assert not thread.is_alive()
    assert len(processes) == 1 and processes[0].poll() is not None
    assert len(errors) == 1 and isinstance(errors[0], Cancelled)

