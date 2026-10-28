"""Train and evaluate the copy classifier.

Labelled pairs (built from data/ by make_dataset.py):
  positive - each copy paired with the original it was made from
  negative - each pair of independent originals, plus each copy paired
             with the other solutions to the same problem (hard negatives:
             same task, different author)

Features: [fingerprint_score, embedding_score], exactly as a run computes them.
Reports precision and recall from stratified 5-fold cross-validation, the
two learned weights, recall per copy kind, and the baseline rule
"flag when max(fingerprint, embedding) >= t" with t tuned on each
training fold. Writes the final model to
backend/codetwin/similarity/models/<embedder>.json.

Run:  python ml/train.py --embedder hashing     (or unixcoder)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from itertools import combinations
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from codetwin.similarity.classifier import model_path_for  # noqa: E402
from codetwin.similarity.embed import cosine_matrix, get_embedder  # noqa: E402
from codetwin.similarity.fingerprint import fingerprint, fingerprint_score  # noqa: E402

THRESHOLD = 0.5


def load_pairs():
    originals = {p.stem: p.read_text() for p in sorted((HERE / "data" / "originals").glob("*.py"))}
    copies = {p.stem: p.read_text() for p in sorted((HERE / "data" / "copies").glob("*.py"))}
    problem = lambda stem: stem.split("_")[0]
    pairs = []   # (name_a, name_b, label, kind)
    for c in copies:
        source, kind = c.split("__")
        pairs.append((c, source, 1, kind))
        for o in originals:
            if o != source and problem(o) == problem(source):
                pairs.append((c, o, 0, "hard_negative"))
    for a, b in combinations(originals, 2):
        pairs.append((a, b, 0, "same_problem" if problem(a) == problem(b) else "different_problem"))
    return {**originals, **copies}, pairs


def features(files: dict[str, str], pairs, embedder) -> np.ndarray:
    names = sorted(files)
    index = {n: i for i, n in enumerate(names)}
    prints = {n: fingerprint(files[n]) for n in names}
    sims = cosine_matrix(embedder.embed([files[n] for n in names]))
    return np.array([[fingerprint_score(prints[a], prints[b]), float(sims[index[a], index[b]])]
                     for a, b, _, _ in pairs])


def best_max_rule_threshold(x, y) -> float:
    scores = x.max(axis=1)
    candidates = np.unique(np.round(scores, 3))
    return max(candidates, key=lambda t: f1_score(y, scores >= t, zero_division=0))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedder", default="hashing", choices=["hashing", "unixcoder"])
    args = parser.parse_args()

    embedder = get_embedder(args.embedder)
    files, pairs = load_pairs()
    x = features(files, pairs, embedder)
    y = np.array([p[2] for p in pairs])
    kinds = np.array([p[3] for p in pairs])

    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    lr_pred = np.zeros_like(y)
    base_pred = np.zeros_like(y)
    for train, test in folds.split(x, y):
        model = LogisticRegression(class_weight="balanced").fit(x[train], y[train])
        lr_pred[test] = model.predict_proba(x[test])[:, 1] >= THRESHOLD
        t = best_max_rule_threshold(x[train], y[train])
        base_pred[test] = x[test].max(axis=1) >= t

    def summary(pred):
        return {
            "precision": round(precision_score(y, pred), 4),
            "recall": round(recall_score(y, pred), 4),
            "f1": round(f1_score(y, pred), 4),
            "recall_by_kind": {k: round(float(pred[(kinds == k)].mean()), 4)
                               for k in ("unchanged", "renamed", "reordered", "restructured", "partial")},
            "false_positive_rate_by_kind": {k: round(float(pred[(kinds == k)].mean()), 4)
                                            for k in ("hard_negative", "same_problem", "different_problem")},
        }

    final = LogisticRegression(class_weight="balanced").fit(x, y)
    w_fp, w_emb = (round(float(w), 4) for w in final.coef_[0])
    version = f"{embedder.name}+lr-{date.today():%Y.%m.%d}"[:40]
    model = {
        "version": version,
        "embedder": args.embedder,
        "coef": [w_fp, w_emb],
        "intercept": round(float(final.intercept_[0]), 4),
        "threshold": THRESHOLD,
        "features": ["fingerprint_score", "embedding_score"],
        "trained_on": {"pairs": len(y), "positives": int(y.sum()), "negatives": int((1 - y).sum())},
    }
    model_path_for(args.embedder).parent.mkdir(parents=True, exist_ok=True)
    model_path_for(args.embedder).write_text(json.dumps(model, indent=2) + "\n")

    def mean_scores(mask):
        return [round(float(v), 3) for v in x[mask].mean(axis=0)]

    metrics = {
        "model": model,
        "cross_validation": "stratified 5-fold, shuffled, seed 42",
        "classifier": summary(lr_pred),
        "baseline_max_rule": summary(base_pred),
        "mean_scores_fp_emb": {k: mean_scores(kinds == k) for k in sorted(set(kinds))},
    }
    out = HERE / "results" / f"metrics_{args.embedder}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
