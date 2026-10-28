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


class AzureBlobStore:
    def __init__(self, connection_string: str, container: str):
        from azure.storage.blob import BlobServiceClient

        self.container = BlobServiceClient.from_connection_string(connection_string).get_container_client(container)

    def put(self, path: str, data: bytes) -> None:
        self.container.upload_blob(str(_safe_relative(path)), data, overwrite=True)

    def get(self, path: str) -> bytes:
        return self.container.download_blob(str(_safe_relative(path))).readall()


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
    """A folder queue. A worker claims a message by renaming it, which is atomic."""

    def __init__(self, root: Path):
        self.root = root / "queue"
        self.root.mkdir(parents=True, exist_ok=True)

    def send(self, body: dict) -> None:
        name = f"{time.time_ns():020d}-{uuid.uuid4().hex[:8]}"
        tmp = self.root / f"{name}.tmp"
        tmp.write_text(json.dumps(body))
        tmp.rename(self.root / f"{name}.msg")

    def receive(self) -> QueueMessage | None:
        for msg in sorted(self.root.glob("*.msg")):
            claimed = msg.with_suffix(f".{os.getpid()}.work")
            try:
                msg.rename(claimed)
            except FileNotFoundError:
                continue  # another worker took it
            return QueueMessage(json.loads(claimed.read_text()), claimed)
        return None

    def delete(self, message: QueueMessage) -> None:
        Path(message.handle).unlink(missing_ok=True)


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
