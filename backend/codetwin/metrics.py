"""Request counts, server errors and response times of this API process, for the platform admin.

Kept in memory for the last hour: nothing is written to disk, and no request body, query string,
token or personal detail is recorded, only the method, the route pattern (for example
/runs/{run_id}), the status and the duration. With several API instances each has its own figures.
"""
from __future__ import annotations

import threading
import time
from collections import deque

WINDOW_SECONDS = 3600


class RequestMetrics:
    def __init__(self, max_requests: int = 20_000, max_errors: int = 50):
        self._requests: deque = deque(maxlen=max_requests)   # (time, duration_ms, status)
        self._errors: deque = deque(maxlen=max_errors)        # recent 5xx: time, method, route, status
        self._lock = threading.Lock()
        self.started = time.time()

    def record(self, method: str, route: str, status: int, duration_ms: float) -> None:
        now = time.time()
        with self._lock:
            self._requests.append((now, duration_ms, status))
            if status >= 500:
                self._errors.append({"at": now, "method": method, "route": route, "status": status})

    def summary(self) -> dict:
        cutoff = time.time() - WINDOW_SECONDS
        with self._lock:
            recent = [r for r in self._requests if r[0] >= cutoff]
            errors = [e for e in self._errors if e["at"] >= cutoff]
        durations = sorted(r[1] for r in recent)

        def pct(q):
            return round(durations[min(len(durations) - 1, int(q * len(durations)))], 1) if durations else None

        return {"window": "last hour, this API process", "requests": len(recent),
                "server_errors": sum(1 for r in recent if r[2] >= 500),
                "client_errors": sum(1 for r in recent if 400 <= r[2] < 500),
                "median_ms": pct(0.5), "p95_ms": pct(0.95),
                "slow_requests_over_2s": sum(1 for d in durations if d > 2000),
                "recent_server_errors": [{**e, "at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(e["at"]))}
                                         for e in errors[-10:]],
                "uptime_seconds": int(time.time() - self.started)}
