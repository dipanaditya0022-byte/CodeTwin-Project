"""The similarity worker: takes run messages off the queue and processes them.

Run with:  python -m codetwin.worker

Started from the same codebase as the API, but as its own process, so a
long run never blocks a web request and the worker can scale on its own.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import contextmanager

from .config import Settings, get_settings
from .db import Database
from .procedures import (FINISHED_AT, ProcedureError, expire_stale_runs, save_run_results, stale_cutoff, utcnow,
                         write_audit)
from .similarity.classifier import CopyClassifier, model_path_for
from .similarity.embed import get_embedder
from .similarity.pipeline import run_similarity
from .stores import WORKER_HEALTH_PATH, Stores, build_stores, manifest_path

log = logging.getLogger("codetwin.worker")


class Worker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings.database_url)
        self.db.init_schema()
        self.stores: Stores = build_stores(settings)
        self.classifier = CopyClassifier.load(settings.model_path or model_path_for(settings.embedder))
        self.embedder = get_embedder(self.classifier.embedder)

    def process_once(self) -> bool:
        """Handle one queued message. Returns False when the queue was empty."""
        message = self.stores.queue.receive()
        if message is None:
            return False
        try:
            self.process_run(int(message.body["run_id"]))
        finally:
            # a failure is recorded on the run itself; the teacher retries from the UI
            try:
                self.stores.queue.delete(message)
            except Exception:   # the message was handed to another worker after its visibility timeout
                log.warning("could not delete queue message for run %s", message.body.get("run_id"))
        return True

    def _claim(self, run_id: int) -> dict | None:
        """Move a run to running, unless it is finished or another live worker already has it."""
        with self.db.transaction() as conn:
            claimed = conn.execute(
                "UPDATE similarity_runs SET status = 'running', heartbeat_at = ?, error_message = NULL"
                " WHERE run_id = ? AND (status = 'queued' OR (status = 'running'"
                " AND (heartbeat_at IS NULL OR heartbeat_at < ?)))",
                [utcnow(), run_id, stale_cutoff(self.settings.run_stale_seconds)]).rowcount
            run = conn.one("SELECT * FROM similarity_runs WHERE run_id = ?", [run_id])
        if claimed != 1:
            # finished, missing, or a live worker already has it (a redelivered queue message)
            log.info("run %s skipped (%s)", run_id, run["status"] if run else "missing")
            return None
        return run

    @contextmanager
    def _heartbeat(self, run_id: int):
        """Report progress every few seconds, so the API can tell a slow run from a dead worker."""
        stop = threading.Event()

        def beat():
            while not stop.wait(self.settings.run_heartbeat_seconds):
                try:
                    with self.db.transaction() as conn:
                        conn.execute("UPDATE similarity_runs SET heartbeat_at = ? WHERE run_id = ?"
                                     " AND status = 'running'", [utcnow(), run_id])
                except Exception:
                    log.exception("heartbeat for run %s failed", run_id)

        thread = threading.Thread(target=beat, daemon=True, name=f"heartbeat-{run_id}")
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=5)

    def process_run(self, run_id: int) -> None:
        run = self._claim(run_id)
        if run is None:
            return
        with self._heartbeat(run_id):
            self._score(run_id, run)

    def _score(self, run_id: int, run: dict) -> None:
        started = time.perf_counter()
        try:
            if run["model_version"] != self.classifier.version:
                raise ModelMismatch(run["model_version"], self.classifier.version)
            with self.db.connect() as conn:
                subs = conn.all("SELECT submission_id, blob_path, file_sha256 FROM submissions"
                                " WHERE assignment_id = ?", [run["assignment_id"]])
                starter_path = conn.scalar("SELECT starter_blob_path FROM assignments WHERE assignment_id = ?",
                                           [run["assignment_id"]])
            # Record exactly which stored file each submission had, so the side-by-side view of this run
            # keeps showing the code that was scored even after a student's file is uploaded again.
            manifest = {
                "run_id": run_id, "starter": starter_path,
                "files": {str(s["submission_id"]): {"blob_path": s["blob_path"], "sha256": s["file_sha256"]}
                          for s in subs}}
            self.stores.blobs.put(manifest_path(run_id), json.dumps(manifest).encode("utf-8"))
            # only this assignment's files are loaded, so both sides of every pair belong to the run's assignment
            files = {s["submission_id"]: self.stores.blobs.get(s["blob_path"]).decode("utf-8") for s in subs}
            starter = self.stores.blobs.get(starter_path).decode("utf-8") if starter_path else None

            result = run_similarity(files, self.classifier, self.embedder, float(run["threshold"]), starter)

            pairs_json = []
            for p in result.pairs:
                doc_id = None
                if p.flagged:
                    doc_id = f"run-{run_id}-{p.a}-{p.b}"
                    self.stores.reports.put({
                        "id": doc_id, "run_id": run_id, "submission_a": p.a, "submission_b": p.b,
                        "fingerprint_score": round(p.fp, 4), "embedding_score": round(p.emb, 4),
                        "copy_probability": round(p.p, 4), "containment_score": round(p.cont, 4),
                        "model_version": run["model_version"], "matches": p.matches})
                pairs_json.append({"a": p.a, "b": p.b, "fp": round(p.fp, 4), "emb": round(p.emb, 4),
                                   "p": round(p.p, 4), "doc": doc_id, "cont": round(p.cont, 4)})
            clusters_json = [{"cluster_no": i, "members": members} for i, members in enumerate(result.clusters, 1)]

            # what makes some files' scores less trustworthy, shown with the results
            manifest["file_notes"] = {str(sid): notes for sid, notes in result.file_notes.items()}
            self.stores.blobs.put(manifest_path(run_id), json.dumps(manifest).encode("utf-8"))

            save_run_results(self.db, run_id, pairs_json, clusters_json)
            log.info("run %s completed: %d files, %d pairs, %d flagged, %d clusters in %.1fs", run_id, len(files),
                     len(result.pairs), sum(p.flagged for p in result.pairs), len(result.clusters),
                     time.perf_counter() - started)
        except Exception as exc:
            log.exception("run %s failed", run_id)
            self._mark_failed(run_id, exc)

    def _mark_failed(self, run_id: int, exc: Exception) -> None:
        with self.db.transaction() as conn:
            now = utcnow()
            conn.execute(f"UPDATE similarity_runs SET status = 'failed', finished_at = {FINISHED_AT}, error_message = ?"
                         " WHERE run_id = ? AND status <> 'completed'", [now, now, failure_message(exc), run_id])
            detail = exc.message if isinstance(exc, ProcedureError) else f"{type(exc).__name__}: {exc}"
            write_audit(conn, None, "run_failed", "similarity_runs", run_id, "running", detail)

    def expire_stale(self) -> None:
        """Fail runs whose worker died (for example a restart mid-run), so teachers can retry them."""
        with self.db.transaction() as conn:
            for run_id in expire_stale_runs(conn, self.settings.run_stale_seconds):
                log.warning("run %s marked failed: its worker stopped responding", run_id)

    def serve(self, idle_seconds: float = 2.0) -> None:
        log.info("worker started with model %s", self.classifier.version)
        self.report_health()
        last_sweep = 0.0
        while True:
            if not self.process_once():
                if time.monotonic() - last_sweep > 60:
                    self.expire_stale()
                    self.report_health()
                    last_sweep = time.monotonic()
                time.sleep(idle_seconds)

    def report_health(self) -> None:
        """Leave a 'last seen' record the platform admin page reads, so an idle worker can be told from a dead one."""
        import socket

        try:
            self.stores.blobs.put(WORKER_HEALTH_PATH, json.dumps({
                "last_seen": utcnow().isoformat(), "model_version": self.classifier.version,
                "host": socket.gethostname(), "pid": os.getpid()}).encode("utf-8"))
        except Exception:
            log.exception("could not write worker health")


class ModelMismatch(Exception):
    def __init__(self, wanted: str, have: str):
        super().__init__(f"run asks for model {wanted} but this worker has {have}")
        self.wanted, self.have = wanted, have


def failure_message(exc: Exception) -> str:
    """A reason the teacher can act on. Technical detail goes to the audit log, not the page."""
    if isinstance(exc, ModelMismatch):
        msg = (f"This run was queued for model {exc.wanted}, but the analysis worker now runs {exc.have}. "
               "Start a new run instead of retrying this one.")
    elif isinstance(exc, ProcedureError):
        msg = f"The results could not be saved: {exc.message} Nothing was saved. Retry the run."
    elif isinstance(exc, (FileNotFoundError, KeyError)):
        msg = ("A submitted file could not be read from storage. Upload the submissions again, "
               "then start a new run.")
    elif isinstance(exc, UnicodeDecodeError):
        msg = "A stored file is not valid UTF-8 text. Upload it again, then start a new run."
    elif isinstance(exc, MemoryError):
        msg = "The analysis ran out of memory. Try again; if it keeps failing, contact the platform admin."
    else:
        msg = (f"The analysis stopped with an unexpected error ({type(exc).__name__}). Nothing was saved. "
               "Retry the run; if it fails again, contact the platform admin.")
    return msg[:500]


def _serve_health(port: int) -> None:
    """App Service restarts a site that does not answer HTTP, so the worker answers one path."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Health(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"worker ok")

        def log_message(self, *args):
            pass

    threading.Thread(target=HTTPServer(("0.0.0.0", port), Health).serve_forever, daemon=True).start()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if os.environ.get("PORT"):
        _serve_health(int(os.environ["PORT"]))
    Worker(get_settings()).serve()


if __name__ == "__main__":
    main()
