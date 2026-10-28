"""Step 5: join flagged pairs that share a submission into clusters (union-find).

Three students who shared one file become one cluster and one review,
not three separate pairs.
"""
from __future__ import annotations


def cluster_pairs(flagged: list[tuple[int, int, float]]) -> list[list[int]]:
    """flagged: (submission_a, submission_b, probability). Returns member lists,
    strongest cluster first (by highest pair probability, then size)."""
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, _ in flagged:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    groups: dict[int, list[int]] = {}
    best: dict[int, float] = {}
    for a, b, p in flagged:
        root = find(a)
        best[root] = max(best.get(root, 0.0), p)
    for node in parent:
        groups.setdefault(find(node), []).append(node)

    ordered = sorted(groups.items(), key=lambda kv: (-best[kv[0]], -len(kv[1]), kv[0]))
    return [sorted(members) for _, members in ordered]
