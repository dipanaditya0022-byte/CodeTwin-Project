"""The whole similarity run: normalise, fingerprint, embed, classify, cluster, explain.

Besides the pairs, a run reports anything about a file that makes its scores less trustworthy
(file_notes), so the owner can see which results to read with care instead of trusting a number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .classifier import CopyClassifier
from .cluster import cluster_pairs
from .embed import cosine_matrix
from .fingerprint import Fingerprint, containment_score, fingerprint, fingerprint_score, matched_regions

# A file with fewer fingerprints than this (after starter code is removed) has too little of its own
# code for a fingerprint score to mean much: one shared line can then look like a large overlap.
MIN_FINGERPRINTS = 12
MOSTLY_STARTER = 0.7   # share of a file's fingerprints that also occur in the starter code


@dataclass
class PairResult:
    a: int
    b: int
    fp: float
    emb: float
    p: float
    flagged: bool
    cont: float | None = None
    matches: list[dict] = field(default_factory=list)


@dataclass
class RunResult:
    pairs: list[PairResult]
    clusters: list[list[int]]
    file_notes: dict[int, list[dict]] = field(default_factory=dict)


def file_notes(prints: dict[int, Fingerprint], exclude: set[int] | None) -> dict[int, list[dict]]:
    """Per submission, the reasons its scores deserve care. Empty for most files."""
    notes: dict[int, list[dict]] = {}
    for sid, fp in prints.items():
        own = fp.selected - exclude if exclude else fp.selected
        found = []
        if not fp.exact:
            found.append({"code": "not_valid_python",
                          "text": "Python could not read this file (for example a syntax error), so it was "
                                  "compared with a simpler reader. Scores involving it are a little less precise."})
        if exclude and fp.selected and len(fp.selected & exclude) / len(fp.selected) >= MOSTLY_STARTER:
            found.append({"code": "mostly_starter",
                          "text": "Most of this file is the starter code, which is ignored, so little is left "
                                  "to compare."})
        if len(own) == 0:
            found.append({"code": "nothing_to_compare",
                          "text": "After removing comments, blank lines and starter code, nothing is left to "
                                  "compare. Its fingerprint scores are 0."})
        elif len(own) < MIN_FINGERPRINTS:
            found.append({"code": "very_short",
                          "text": f"Very little code of its own ({len(own)} fingerprints). A few shared lines "
                                  "can make it look similar to others; read its matches before acting."})
        if found:
            notes[sid] = found
    return notes


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
        cont = containment_score(prints[a], prints[b], exclude)
        emb = float(sims[pos[a], pos[b]])
        p = classifier.probability(fp, emb, cont if classifier.uses_containment else None)
        pairs.append(PairResult(a, b, fp, emb, p, p >= threshold, cont))

    for pair in pairs:
        if pair.flagged:
            pair.matches = matched_regions(prints[pair.a], prints[pair.b], exclude=exclude)

    clusters = cluster_pairs([(x.a, x.b, x.p) for x in pairs if x.flagged])
    return RunResult(pairs, clusters, file_notes(prints, exclude))
