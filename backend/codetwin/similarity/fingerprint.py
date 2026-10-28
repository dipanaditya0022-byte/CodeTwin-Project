"""Step 2: k-gram fingerprints with winnowing (Schleimer, Wilkerson and Aiken, 2003).

Every run of K consecutive normalised tokens is hashed; winnowing keeps
the smallest hash in each window of W hashes. Any shared run of at least
W + K - 1 tokens is guaranteed to produce a shared fingerprint. The
fingerprint score is the Jaccard share of fingerprints two files have in
common.

The same k-gram hashes also give the matched line ranges for the
side-by-side view (the "explain" step).
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field

from .normalize import Tok, normalize

K = 5        # tokens per k-gram
W = 4        # winnowing window, in hashes
MAX_POSTINGS = 50   # skip a k-gram that occurs more often than this when matching lines


def _hash(tokens: list[str]) -> int:
    return int.from_bytes(hashlib.blake2b(" ".join(tokens).encode(), digest_size=8).digest(), "big")


@dataclass
class Fingerprint:
    tokens: list[Tok]
    hashes: list[int]                     # one per k-gram, in order
    selected: set[int] = field(default_factory=set)   # winnowed fingerprints


def winnow(hashes: list[int], w: int = W) -> set[int]:
    if len(hashes) <= w:
        return set(hashes)
    chosen: set[int] = set()
    last = -1
    for start in range(len(hashes) - w + 1):
        window = hashes[start:start + w]
        low = min(window)
        pos = start + max(i for i, h in enumerate(window) if h == low)   # rightmost minimum
        if pos != last:
            chosen.add(hashes[pos])
            last = pos
    return chosen


def fingerprint(source: str, k: int = K, w: int = W) -> Fingerprint:
    toks = normalize(source)
    texts = [t.text for t in toks]
    hashes = [_hash(texts[i:i + k]) for i in range(len(texts) - k + 1)]
    return Fingerprint(toks, hashes, winnow(hashes, w))


def fingerprint_score(a: Fingerprint, b: Fingerprint, exclude: set[int] | None = None) -> float:
    """Jaccard similarity of the two fingerprint sets, ignoring excluded (starter code) hashes."""
    sa = a.selected - exclude if exclude else a.selected
    sb = b.selected - exclude if exclude else b.selected
    union = len(sa | sb)
    return len(sa & sb) / union if union else 0.0


def matched_regions(a: Fingerprint, b: Fingerprint, k: int = K, min_tokens: int = 2 * K,
                    exclude: set[int] | None = None) -> list[dict]:
    """Longest non-overlapping blocks of identical normalised tokens, as line ranges.

    Returns [{"a_lines": [12, 31], "b_lines": [8, 27], "tokens": 146}, ...], largest first.
    """
    index: dict[int, list[int]] = defaultdict(list)
    for i, h in enumerate(a.hashes):
        if not exclude or h not in exclude:
            index[h].append(i)

    diagonals: dict[int, list[int]] = defaultdict(list)   # (i - j) -> positions i in A
    for j, h in enumerate(b.hashes):
        hits = index.get(h)
        if hits and len(hits) <= MAX_POSTINGS:
            for i in hits:
                diagonals[i - j].append(i)

    blocks = []   # (length, a_start, b_start)
    for diag, positions in diagonals.items():
        positions.sort()
        start = prev = positions[0]
        for i in positions[1:] + [None]:
            if i is not None and i == prev + 1:
                prev = i
                continue
            length = prev - start + k
            if length >= min_tokens:
                blocks.append((length, start, start - diag))
            if i is not None:
                start = prev = i

    blocks.sort(reverse=True)
    used_a: set[int] = set()
    used_b: set[int] = set()
    out = []
    for length, sa, sb in blocks:
        ra, rb = range(sa, sa + length), range(sb, sb + length)
        if used_a.intersection(ra) or used_b.intersection(rb):
            continue
        used_a.update(ra)
        used_b.update(rb)
        out.append({
            "a_lines": [a.tokens[sa].line, a.tokens[sa + length - 1].line],
            "b_lines": [b.tokens[sb].line, b.tokens[sb + length - 1].line],
            "tokens": length,
        })
    return out
