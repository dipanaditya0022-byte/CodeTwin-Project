"""Time a whole similarity run against the performance target (60 files within 5 minutes).

Run:  python ml/benchmark.py --embedder hashing --files 60 120
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from codetwin.similarity.classifier import CopyClassifier, model_path_for  # noqa: E402
from codetwin.similarity.embed import get_embedder  # noqa: E402
from codetwin.similarity.pipeline import run_similarity  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedder", default="hashing", choices=["hashing", "unixcoder"])
    parser.add_argument("--files", type=int, nargs="+", default=[60, 120])
    args = parser.parse_args()

    pool = [p.read_text() for p in sorted((HERE / "data").glob("*/*.py"))]
    classifier = CopyClassifier.load(model_path_for(args.embedder))
    t0 = time.perf_counter()
    embedder = get_embedder(args.embedder)
    print(f"{args.embedder}: model load {time.perf_counter() - t0:.1f}s")
    for n in args.files:
        files = {i + 1: pool[i % len(pool)] for i in range(n)}
        t0 = time.perf_counter()
        result = run_similarity(files, classifier, embedder, classifier.threshold)
        elapsed = time.perf_counter() - t0
        print(f"  {n} files, {len(result.pairs)} pairs: {elapsed:.1f}s "
              f"({sum(p.flagged for p in result.pairs)} flagged) - target 300s: {'PASS' if elapsed < 300 else 'FAIL'}")


if __name__ == "__main__":
    main()
