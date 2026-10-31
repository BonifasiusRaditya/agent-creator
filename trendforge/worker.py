"""The video worker: claims queued jobs from the database and runs them.

Embedded (default for local use): started by the website process.
Separate (online deployment): ``python -m trendforge.worker`` on a machine with
FFmpeg and the speech model, sharing the same database and object storage.
"""
import logging
import os
import signal
import socket
import threading
import time
import uuid
from pathlib import Path

from .media import Cancelled, MediaWorker, ffmpeg  # noqa: F401  (Cancelled re-exported for tests)

log = logging.getLogger("trendforge.worker")
LANES = ("media", "light")


class WorkerRuntime:
    def __init__(self, db, settings, storage, scratch, lanes=LANES, poll_seconds=None,
                 lease_seconds=60, heartbeat_seconds=2.0, worker_id=None):
        self.db, self.settings, self.storage = db, settings, storage
        self.scratch = Path(scratch)
        self.media = MediaWorker(db, settings, storage, self.scratch)
        self.lanes = lanes
        self.poll = poll_seconds if poll_seconds is not None else float(os.environ.get("TRENDFORGE_WORKER_POLL_SECONDS", "1"))
        # When idle, poll less often (fewer database queries); a new job wakes an embedded worker at once.
        self.max_idle = max(self.poll, float(os.environ.get("TRENDFORGE_WORKER_MAX_IDLE_SECONDS", "5")))
        self.wakeup = threading.Event()
        self.media.wake = self.wake  # A finished edit queues its own preparation job.
        self.lease, self.heartbeat_seconds = lease_seconds, heartbeat_seconds
        self.id = worker_id or f"wkr_{socket.gethostname()[:20]}_{os.getpid()}_{uuid.uuid4().hex[:6]}"
        self.stopping = threading.Event()
        self.running = {}  # job id -> cancel event
        self.lock = threading.Lock()
        self.threads = []

    # Life cycle ------------------------------------------------------------------

    def start(self, sole_worker=False):
        """sole_worker: this is the only worker, so jobs left running by a dead process fail now
        instead of after their lease expires."""
        if sole_worker:
            self.db.interrupt_jobs()
        self.report()
        for target, args in [(self.loop, (lane,)) for lane in self.lanes] + [(self.presence, ())]:
            thread = threading.Thread(target=target, args=args, daemon=True, name=f"trendforge-{target.__name__}-{args[0] if args else ''}")
            thread.start()
            self.threads.append(thread)
        return self

    def wake(self):
        self.wakeup.set()

    def stop(self, timeout=30):
        self.stopping.set()
        self.wakeup.set()
        with self.lock:
            for event in self.running.values():
                event.set()
        for thread in self.threads:
            thread.join(timeout=timeout)
        self.threads = []

    # Work ------------------------------------------------------------------------

    def loop(self, lane):
        last_recovery, idle = 0.0, self.poll
        while not self.stopping.is_set():
            try:
                if time.monotonic() - last_recovery > 15:
                    self.db.recover_expired_jobs()
                    last_recovery = time.monotonic()
                job = self.db.claim_job(lane, self.id, self.lease)
                if job:
                    self.execute(job)
                    idle = self.poll
                    continue
            except Exception:
                log.exception("Worker loop error (lane %s)", lane)
            if self.wakeup.wait(idle):
                self.wakeup.clear()
                idle = self.poll
            else:
                idle = min(idle * 2, self.max_idle)

    def execute(self, job):
        event, done = threading.Event(), threading.Event()
        with self.lock:
            self.running[job["id"]] = event
        beat = threading.Thread(target=self.renew, args=(job["id"], event, done), daemon=True)
        beat.start()
        try:
            self.media.run(job, event)
        finally:
            done.set()
            beat.join(timeout=10)
            with self.lock:
                self.running.pop(job["id"], None)

    def renew(self, jid, event, done):
        """Keep the lease alive and notice cancellation requested through the website."""
        while not done.wait(self.heartbeat_seconds):
            try:
                status = self.db.heartbeat(jid, self.id, self.lease)
            except Exception:
                continue  # A brief database outage must not stop the render; the lease has slack.
            if status in (None, "cancelling", "cancelled"):
                event.set()

    def cancel_local(self, jid):
        with self.lock:
            event = self.running.get(jid)
        if event:
            event.set()

    # Presence --------------------------------------------------------------------

    def report(self):
        models = self.scratch / "models"
        self.db.worker_seen(self.id, {
            "lanes": list(self.lanes), "storage": self.storage.backend,
            "ffmpeg": bool(Path(ffmpeg()).is_file()),
            "models_ready": [m for m in ("tiny", "base", "small") if (models / f".ready-{m}").exists()],
            "running": list(self.running)})

    def presence(self):
        while not self.stopping.wait(15):
            try:
                self.report()
                self.purge_logs()
            except Exception:
                log.exception("Worker presence update failed")

    def purge_logs(self):
        cutoff = time.time() - 7 * 86400
        for pattern in ("logs/*.log", "jobs/*/process.log"):
            for item in self.scratch.glob(pattern):
                try:
                    if item.stat().st_mtime < cutoff:
                        item.unlink(missing_ok=True)
                except OSError:
                    pass


def main():
    import argparse

    from .config import DATA, Settings
    from .db import Database
    from .storage import create_storage

    parser = argparse.ArgumentParser(description="Run the TrendForge video worker")
    parser.add_argument("--scratch", default=os.environ.get("TRENDFORGE_WORKER_DIR") or str(DATA),
                        help="Working folder for FFmpeg files and speech models")
    parser.add_argument("--sole-worker", action="store_true",
                        help="Fail jobs left running by a previous worker at start-up (only one worker exists)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    scratch = Path(args.scratch).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    db = Database(scratch / "trendforge.sqlite3")
    runtime = WorkerRuntime(db, Settings(scratch), create_storage(scratch), scratch)
    stop = threading.Event()
    for name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: stop.set())
    runtime.start(sole_worker=args.sole_worker)
    log.info("Worker %s started (database: %s, storage: %s)", runtime.id, db.backend, runtime.storage.backend)
    while not stop.wait(1):
        pass
    log.info("Stopping; running jobs are cancelled and can be started again.")
    runtime.stop()


if __name__ == "__main__":
    main()
