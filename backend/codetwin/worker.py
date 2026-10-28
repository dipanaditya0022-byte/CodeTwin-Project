"""The similarity worker: takes run messages off the queue and processes them.

Run with:  python -m codetwin.worker

Started from the same codebase as the API, but as its own process, so a
long run never blocks a web request and the worker can scale on its own.
"""
from __future__ import annotations

import logging
import os
import threading
import time

from .config import Settings, get_settings
from .db import Database
from .procedures import ProcedureError, save_run_results, utcnow, write_audit
from .similarity.classifier import CopyClassifier, model_path_for
from .similarity.embed import get_embedder
from .similarity.pipeline import run_similarity
from .stores import Stores, build_stores

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
            self.stores.queue.delete(message)
        return True

    def process_run(self, run_id: int) -> None:
        with self.db.transaction() as conn:
            run = conn.one("SELECT * FROM similarity_runs WHERE run_id = ?", [run_id])
            if run is None or run["status"] not in ("queued", "running"):
                log.info("run %s skipped (missing or already %s)", run_id, run and run["status"])
                return
            conn.execute("UPDATE similarity_runs SET status = 'running' WHERE run_id = ?", [run_id])

        started = time.perf_counter()
        try:
            if run["model_version"] != self.classifier.version:
                raise RuntimeError(f"run asks for model {run['model_version']} but this worker has "
                                   f"{self.classifier.version}")
            with self.db.connect() as conn:
                subs = conn.all("SELECT submission_id, blob_path FROM submissions WHERE assignment_id = ?",
                                [run["assignment_id"]])
                starter_path = conn.scalar("SELECT starter_blob_path FROM assignments WHERE assignment_id = ?",
                                           [run["assignment_id"]])
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
                        "copy_probability": round(p.p, 4), "model_version": run["model_version"],
                        "matches": p.matches})
                pairs_json.append({"a": p.a, "b": p.b, "fp": round(p.fp, 4), "emb": round(p.emb, 4),
                                   "p": round(p.p, 4), "doc": doc_id})
            clusters_json = [{"cluster_no": i, "members": members} for i, members in enumerate(result.clusters, 1)]

            save_run_results(self.db, run_id, pairs_json, clusters_json)
            log.info("run %s completed: %d files, %d pairs, %d flagged, %d clusters in %.1fs", run_id, len(files),
                     len(result.pairs), sum(p.flagged for p in result.pairs), len(result.clusters),
                     time.perf_counter() - started)
        except Exception as exc:
            log.exception("run %s failed", run_id)
            self._mark_failed(run_id, exc)

    def _mark_failed(self, run_id: int, exc: Exception) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE similarity_runs SET status = 'failed', finished_at = ? WHERE run_id = ?"
                         " AND status <> 'completed'", [utcnow(), run_id])
            detail = exc.message if isinstance(exc, ProcedureError) else f"{type(exc).__name__}: {exc}"
            write_audit(conn, None, "run_failed", "similarity_runs", run_id, "running", detail)

    def serve(self, idle_seconds: float = 2.0) -> None:
        log.info("worker started with model %s", self.classifier.version)
        while True:
            if not self.process_once():
                time.sleep(idle_seconds)


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
