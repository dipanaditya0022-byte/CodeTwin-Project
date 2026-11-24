"""Train and evaluate the copy classifier.

Labelled pairs (built from data/ by make_dataset.py):
  positive - each copy paired with the original it was made from
  negative - each pair of independent originals, plus each copy paired
             with the other solutions to the same problem (hard negatives:
             same task, different author)

Features, exactly as a run computes them:
  fingerprint_score  Jaccard share of winnowed fingerprints
  embedding_score    cosine similarity of the embeddings
  containment_score  share of the smaller file's fingerprints found in the other
                     (catches a copied block inside a larger file; --features 2 leaves it out)

Evaluation. The headline numbers come from 5-fold cross-validation grouped by problem: every
pair about one problem is in the same fold, so a model is always tested on problems it never saw.
Stratified 5-fold by pair (the earlier method, which lets one problem appear on both sides) is
reported too. Also reported: the baseline rule "flag when max(fingerprint, embedding) >= t",
recall per copy kind, false positives per kind of honest pair, and a table of operating points
(precision, recall, partial-copy recall and false positives per 1,000 honest pairs) for a range
of thresholds, so a run's threshold can be chosen knowingly.

ALL OF THIS IS SYNTHETIC: the copies are machine-made from 30 hand-written originals. It shows
what the method can separate, not how it does on real student code.

Writes the final model (trained on every pair) to backend/codetwin/similarity/models/<embedder>.json.

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
from sklearn.model_selection import GroupKFold, StratifiedKFold

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from codetwin.similarity.classifier import FEATURES, model_path_for  # noqa: E402
from codetwin.similarity.embed import cosine_matrix, get_embedder  # noqa: E402
from codetwin.similarity.fingerprint import containment_score, fingerprint, fingerprint_score  # noqa: E402

THRESHOLD = 0.5
OPERATING_POINTS = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
COPY_KINDS = ("unchanged", "renamed", "reordered", "restructured", "partial")
HONEST_KINDS = ("hard_negative", "same_problem", "different_problem")


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
    """One row per pair: fingerprint, embedding, containment (columns in FEATURES order)."""
    names = sorted(files)
    index = {n: i for i, n in enumerate(names)}
    prints = {n: fingerprint(files[n]) for n in names}
    sims = cosine_matrix(embedder.embed([files[n] for n in names]))
    return np.array([[fingerprint_score(prints[a], prints[b]), float(sims[index[a], index[b]]),
                      containment_score(prints[a], prints[b])] for a, b, _, _ in pairs])


def best_max_rule_threshold(x, y) -> float:
    scores = x.max(axis=1)
    candidates = np.unique(np.round(scores, 3))
    return max(candidates, key=lambda t: f1_score(y, scores >= t, zero_division=0))


def cross_validate(x, y, splits) -> tuple[np.ndarray, np.ndarray]:
    """Out-of-fold copy probabilities from the classifier, and predictions from the tuned baseline rule."""
    prob = np.zeros(len(y))
    base = np.zeros_like(y)
    for train, test in splits:
        model = LogisticRegression(class_weight="balanced").fit(x[train], y[train])
        prob[test] = model.predict_proba(x[test])[:, 1]
        t = best_max_rule_threshold(x[train][:, :2], y[train])
        base[test] = x[test][:, :2].max(axis=1) >= t
    return prob, base


def summary(y, kinds, pred) -> dict:
    honest = y == 0
    return {
        "precision": round(precision_score(y, pred, zero_division=0), 4),
        "recall": round(recall_score(y, pred), 4),
        "f1": round(f1_score(y, pred), 4),
        "false_positive_rate": round(float(pred[honest].mean()), 4),
        "false_positives": int(pred[honest].sum()),
        "recall_by_kind": {k: round(float(pred[kinds == k].mean()), 4) for k in COPY_KINDS},
        "false_positives_by_kind": {k: int(pred[kinds == k].sum()) for k in HONEST_KINDS},
    }


def operating_points(y, kinds, prob) -> list[dict]:
    points = []
    for t in OPERATING_POINTS:
        pred = (prob >= t).astype(int)
        honest = y == 0
        points.append({
            "threshold": t,
            "precision": round(precision_score(y, pred, zero_division=0), 3),
            "recall": round(recall_score(y, pred), 3),
            "partial_recall": round(float(pred[kinds == "partial"].mean()), 3),
            "false_positives_per_1000_honest_pairs": round(1000 * float(pred[honest].mean()), 1),
        })
    return points


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedder", default="hashing", choices=["hashing", "unixcoder"])
    parser.add_argument("--features", type=int, default=3, choices=[2, 3],
                        help="3 adds the containment score; 2 is the original two-score model")
    args = parser.parse_args()

    embedder = get_embedder(args.embedder)
    files, pairs = load_pairs()
    x_all = features(files, pairs, embedder)
    names = list(FEATURES[:args.features])
    x = x_all[:, :args.features]
    y = np.array([p[2] for p in pairs])
    kinds = np.array([p[3] for p in pairs])
    problems = np.array([p[0].split("_")[0] for p in pairs])

    grouped = list(GroupKFold(n_splits=5).split(x, y, problems))
    stratified = list(StratifiedKFold(n_splits=5, shuffle=True, random_state=42).split(x, y))
    g_prob, g_base = cross_validate(x, y, grouped)
    s_prob, s_base = cross_validate(x, y, stratified)

    final = LogisticRegression(class_weight="balanced").fit(x, y)
    version = f"{embedder.name}{'+cont' if args.features == 3 else ''}+lr-{date.today():%Y.%m.%d}"[:40]
    points = operating_points(y, kinds, g_prob)
    model = {
        "version": version,
        "embedder": args.embedder,
        "features": names,
        "coef": [round(float(w), 4) for w in final.coef_[0]],
        "intercept": round(float(final.intercept_[0]), 4),
        "threshold": THRESHOLD,
        "trained_on": {"pairs": len(y), "positives": int(y.sum()), "negatives": int((1 - y).sum()),
                       "data": "synthetic: copies machine-made from 30 hand-written originals"},
        "operating_points": points,
        "operating_points_from": "5-fold cross-validation grouped by problem, synthetic data",
    }
    model_path_for(args.embedder).parent.mkdir(parents=True, exist_ok=True)
    model_path_for(args.embedder).write_text(json.dumps(model, indent=2) + "\n")

    def mean_scores(mask):
        return {f: round(float(v), 3) for f, v in zip(FEATURES, x_all[mask].mean(axis=0))}

    metrics = {
        "model": model,
        "data": "SYNTHETIC. Copies are generated by rewriting 30 hand-written originals; no real student code.",
        "headline": "classifier at threshold 0.5, cross-validated by problem",
        "grouped_by_problem": {"method": "GroupKFold(5) on the problem id",
                               "classifier": summary(y, kinds, (g_prob >= THRESHOLD).astype(int)),
                               "baseline_max_rule": summary(y, kinds, g_base)},
        "stratified_by_pair": {"method": "StratifiedKFold(5), shuffled, seed 42",
                               "classifier": summary(y, kinds, (s_prob >= THRESHOLD).astype(int)),
                               "baseline_max_rule": summary(y, kinds, s_base)},
        "operating_points": points,
        "mean_scores_by_kind": {k: mean_scores(kinds == k) for k in sorted(set(kinds))},
    }
    out = HERE / "results" / f"metrics_{args.embedder}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps({k: metrics[k] for k in ("grouped_by_problem", "operating_points")}, indent=2))


if __name__ == "__main__":
    main()
