"""The whole similarity run: normalise, fingerprint, embed, classify, cluster, explain."""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .classifier import CopyClassifier
from .cluster import cluster_pairs
from .embed import cosine_matrix
from .fingerprint import fingerprint, fingerprint_score, matched_regions


@dataclass
class PairResult:
    a: int
    b: int
    fp: float
    emb: float
    p: float
    flagged: bool
    matches: list[dict] = field(default_factory=list)


@dataclass
class RunResult:
    pairs: list[PairResult]
    clusters: list[list[int]]


def run_similarity(files: dict[int, str], classifier: CopyClassifier, embedder, threshold: float,
                   starter_code: str | None = None) -> RunResult:
    """files maps submission_id -> source text. Every unordered pair is scored once (a < b)."""
    ids = sorted(files)
    prints = {sid: fingerprint(files[sid]) for sid in ids}
    exclude = None
    if starter_code:
        starter = fingerprint(starter_code)
        exclude = set(starter.hashes)   # code every student was given is not evidence

    sims = cosine_matrix(embedder.embed([files[sid] for sid in ids])) if ids else None
    pos = {sid: i for i, sid in enumerate(ids)}

    pairs: list[PairResult] = []
    for a, b in combinations(ids, 2):
        fp = fingerprint_score(prints[a], prints[b], exclude)
        emb = float(sims[pos[a], pos[b]])
        p = classifier.probability(fp, emb)
        pairs.append(PairResult(a, b, fp, emb, p, p >= threshold))

    for pair in pairs:
        if pair.flagged:
            pair.matches = matched_regions(prints[pair.a], prints[pair.b], exclude=exclude)

    clusters = cluster_pairs([(x.a, x.b, x.p) for x in pairs if x.flagged])
    return RunResult(pairs, clusters)
