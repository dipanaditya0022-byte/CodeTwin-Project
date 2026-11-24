"""File store, match-report store and job queue.

Each has a local implementation (folders under data_dir, used in
development and tests) and an Azure implementation (Blob Storage,
Cosmos DB, Storage Queue) chosen by CODETWIN_STORAGE_BACKEND.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .config import Settings


def _safe_relative(path: str) -> PurePosixPath:
    """Blob paths are built by the server, but refuse traversal all the same."""
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError(f"unsafe blob path: {path!r}")
    return p


# ---------------------------------------------------------------- blobs

class LocalBlobStore:
    def __init__(self, root: Path):
        self.root = root / "blobs"

    def put(self, path: str, data: bytes) -> None:
        target = self.root / _safe_relative(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def get(self, path: str) -> bytes:
        return (self.root / _safe_relative(path)).read_bytes()

    def delete(self, path: str) -> None:
        (self.root / _safe_relative(path)).unlink(missing_ok=True)


class AzureBlobStore:
    def __init__(self, connection_string: str, container: str):
        from azure.storage.blob import BlobServiceClient

        self.container = BlobServiceClient.from_connection_string(connection_string).get_container_client(container)

    def put(self, path: str, data: bytes) -> None:
        self.container.upload_blob(str(_safe_relative(path)), data, overwrite=True)

    def get(self, path: str) -> bytes:
        return self.container.download_blob(str(_safe_relative(path))).readall()

    def delete(self, path: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            self.container.delete_blob(str(_safe_relative(path)))
        except ResourceNotFoundError:
            pass


WORKER_HEALTH_PATH = "health/worker.json"   # written by the worker about once a minute


def manifest_path(run_id: int) -> str:
    """The blob that records which stored file each submission had when a run scored it."""
    return f"runs/{run_id}/manifest.json"


# ---------------------------------------------------------------- match reports

class LocalReportStore:
    def __init__(self, root: Path):
        self.root = root / "reports"

    def _file(self, doc_id: str) -> Path:
        return self.root / f"{_safe_relative(doc_id).name}.json"

    def put(self, doc: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._file(doc["id"]).write_text(json.dumps(doc))

    def get(self, doc_id: str, run_id: int) -> dict | None:
        f = self._file(doc_id)
        return json.loads(f.read_text()) if f.exists() else None


class CosmosReportStore:
    """Match reports in Cosmos DB, partitioned by run_id."""

    def __init__(self, url: str, key: str, database: str, container: str):
        from azure.cosmos import CosmosClient

        self.container = CosmosClient(url, credential=key).get_database_client(database).get_container_client(container)

    def put(self, doc: dict) -> None:
        self.container.upsert_item(doc)

    def get(self, doc_id: str, run_id: int) -> dict | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        try:
            return self.container.read_item(doc_id, partition_key=run_id)
        except CosmosResourceNotFoundError:
            return None


# ---------------------------------------------------------------- queue

@dataclass
class QueueMessage:
    body: dict
    handle: object


class LocalQueue:
    """A folder queue. A worker claims a message by renaming it, which is atomic.

    Like the Azure queue, a claimed message comes back after a visibility timeout if the worker
    that claimed it never deleted it (for example because the process was killed mid-run).
    """

    def __init__(self, root: Path, visibility_timeout: float = 600):
        self.root = root / "queue"
        self.root.mkdir(parents=True, exist_ok=True)
        self.visibility_timeout = visibility_timeout

    def send(self, body: dict) -> None:
        name = f"{time.time_ns():020d}-{uuid.uuid4().hex[:8]}"
        tmp = self.root / f"{name}.tmp"
        tmp.write_text(json.dumps(body))
        tmp.rename(self.root / f"{name}.msg")

    def receive(self) -> QueueMessage | None:
        self._release_abandoned()
        for msg in sorted(self.root.glob("*.msg")):
            claimed = self.root / f"{msg.stem}.{os.getpid()}-{uuid.uuid4().hex[:6]}.work"
            try:
                msg.rename(claimed)
            except FileNotFoundError:
                continue  # another worker took it
            os.utime(claimed)   # the claim time, which the visibility timeout counts from
            return QueueMessage(json.loads(claimed.read_text()), claimed)
        return None

    def _release_abandoned(self) -> None:
        cutoff = time.time() - self.visibility_timeout
        for work in self.root.glob("*.work"):
            try:
                if work.stat().st_mtime < cutoff:
                    work.rename(self.root / f"{work.name.split('.')[0]}.msg")
            except FileNotFoundError:
                continue  # finished or released by another worker meanwhile

    def delete(self, message: QueueMessage) -> None:
        Path(message.handle).unlink(missing_ok=True)

    def depth(self) -> dict:
        return {"waiting": len(list(self.root.glob("*.msg"))), "in_progress": len(list(self.root.glob("*.work")))}


class AzureQueue:
    def __init__(self, connection_string: str, queue_name: str):
        from azure.storage.queue import QueueClient

        self.client = QueueClient.from_connection_string(connection_string, queue_name)

    def send(self, body: dict) -> None:
        self.client.send_message(json.dumps(body))

    def receive(self) -> QueueMessage | None:
        # a run of 60 files takes well under 10 minutes; if the worker dies the message reappears
        for msg in self.client.receive_messages(max_messages=1, visibility_timeout=600):
            return QueueMessage(json.loads(msg.content), msg)
        return None

    def delete(self, message: QueueMessage) -> None:
        self.client.delete_message(message.handle)

    def depth(self) -> dict:
        # Azure reports an approximate count of all messages, including ones a worker holds
        return {"waiting": self.client.get_queue_properties().approximate_message_count, "in_progress": None}


# ---------------------------------------------------------------- factory

@dataclass
class Stores:
    blobs: LocalBlobStore | AzureBlobStore
    reports: LocalReportStore | CosmosReportStore
    queue: LocalQueue | AzureQueue


def build_stores(settings: Settings) -> Stores:
    if settings.storage_backend == "azure":
        conn = settings.azure_storage_connection_string
        return Stores(
            blobs=AzureBlobStore(conn, settings.blob_container),
            reports=CosmosReportStore(settings.cosmos_url, settings.cosmos_key,
                                      settings.cosmos_database, settings.cosmos_container),
            queue=AzureQueue(conn, settings.queue_name),
        )
    root = Path(settings.data_dir)
    return Stores(LocalBlobStore(root), LocalReportStore(root), LocalQueue(root))
