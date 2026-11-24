import pytest
from conftest import source

from codetwin.similarity.classifier import CopyClassifier, model_path_for
from codetwin.similarity.cluster import cluster_pairs
from codetwin.similarity.embed import HashingEmbedder
from codetwin.similarity.fingerprint import (containment_score, fingerprint, fingerprint_score, matched_regions,
                                             winnow)
from codetwin.similarity.normalize import normalize
from codetwin.similarity.pipeline import run_similarity

ORIGINAL = """
def average(values):
    total = 0
    for v in values:
        total += v
    return total / len(values)

print(average([1, 2, 3]))
"""

RENAMED = """
# my own work
def mean(nums):

    s = 0   # running sum
    for n in nums:
        s += n
    return s / len(nums)

print(mean([4, 5, 6]))
"""


def test_renaming_comments_and_blank_lines_do_not_change_tokens():
    assert [t.text for t in normalize(ORIGINAL)] == [t.text for t in normalize(RENAMED)]


def test_literals_and_identifiers_are_replaced_but_keywords_kept():
    texts = [t.text for t in normalize("for i in range(10): x = 'a'")]
    assert texts == ["for", "ID", "in", "ID", "(", "LIT", ")", ":", "ID", "=", "LIT"]


def test_fstrings_become_one_literal():
    assert [t.text for t in normalize('print(f"{a} and {b}")')] == ["ID", "(", "LIT", ")"]


def test_broken_code_still_tokenises():
    assert len(normalize("def f(:\n  return )) 'unterminated")) > 3


def test_renamed_copy_scores_one_and_unrelated_code_scores_low():
    assert fingerprint_score(fingerprint(ORIGINAL), fingerprint(RENAMED)) == 1.0
    other = fingerprint(source("p03_primes_b"))
    assert fingerprint_score(fingerprint(ORIGINAL), other) < 0.2


def test_winnowing_keeps_a_subset_and_is_deterministic():
    hashes = fingerprint(source("p02_matmul_a")).hashes
    chosen = winnow(hashes)
    assert chosen <= set(hashes) and 0 < len(chosen) < len(hashes)
    assert chosen == winnow(hashes)


def test_matched_regions_report_line_ranges():
    a, b = fingerprint(source("p10_sort_a")), fingerprint(source("p10_sort_a__renamed"))
    regions = matched_regions(a, b)
    assert regions and regions[0]["tokens"] >= 50
    first = regions[0]
    assert first["a_lines"][0] <= first["a_lines"][1] and first["b_lines"][0] <= first["b_lines"][1]


def test_starter_code_is_excluded():
    starter = "def read_numbers():\n    return [int(x) for x in input().split()]\n"
    a = starter + "print(sum(read_numbers()))\n"
    b = starter + "nums = read_numbers()\nprint(max(nums) - min(nums))\n"
    fa, fb = fingerprint(a), fingerprint(b)
    exclude = set(fingerprint(starter).hashes)
    assert fingerprint_score(fa, fb, exclude) < fingerprint_score(fa, fb)


def test_embedding_ignores_statement_order():
    e = HashingEmbedder()
    v = e.embed([source("p04_bank_a"), source("p04_bank_a__reordered"), source("p03_primes_a")])
    assert v[0] @ v[1] > 0.9 > v[0] @ v[2]


def test_clusters_join_pairs_that_share_a_submission():
    clusters = cluster_pairs([(1, 2, 0.9), (2, 3, 0.8), (7, 9, 0.99)])
    assert clusters == [[7, 9], [1, 2, 3]]


def test_trained_model_is_monotonic_in_every_score():
    model = CopyClassifier.load(model_path_for("hashing"))
    assert model.uses_containment and all(w > 0 for w in model.weights)   # every score pushes towards 'copy'
    assert model.probability(0.9, 0.95, 0.95) > model.threshold > model.probability(0.05, 0.6, 0.1)
    with pytest.raises(ValueError):
        model.probability(0.9, 0.95)   # a three-score model cannot silently drop a score


def test_two_score_models_still_load_and_score():
    # a retired October model: runs it scored must stay explainable
    model = CopyClassifier.load(model_path_for("unixcoder").parent / "archive" / "unixcoder-canon+lr-2026.10.28.json")
    assert not model.uses_containment and len(model.weights) == 2
    assert model.probability(0.9, 0.95) > model.threshold > model.probability(0.05, 0.6)


def test_explanation_parts_add_up_to_the_probability():
    model = CopyClassifier.load(model_path_for("hashing"))
    scores = {"fingerprint_score": 0.4, "embedding_score": 0.8, "containment_score": 0.7}
    e = model.explain(scores)
    assert abs(e["probability"] - model.probability(0.4, 0.8, 0.7)) < 1e-3
    assert e["main_reason"] == max(e["parts"], key=lambda p: p["contribution"])["label"]
    assert len(e["parts"]) == 3


def test_containment_catches_a_block_copied_into_a_larger_file():
    original = source("p10_sort_a")
    padded = original + "\n\n" + source("p08_stats_b") + "\n" + source("p03_primes_c")
    a, b = fingerprint(original), fingerprint(padded)
    assert containment_score(a, b) > 0.9 > fingerprint_score(a, b) * 2


def test_file_notes_explain_unreliable_files():
    from codetwin.similarity.pipeline import file_notes

    starter = source("p08_stats_a")   # a teacher's template the student barely changed
    prints = {1: fingerprint("x = (\n"), 2: fingerprint("print(1)\n"), 3: fingerprint(source("p10_sort_a")),
              4: fingerprint(starter + "\nresult = 1\n")}
    notes = file_notes(prints, set(fingerprint(starter).hashes))
    codes = {sid: {n["code"] for n in v} for sid, v in notes.items()}
    assert "not_valid_python" in codes[1]
    assert "very_short" in codes[2] or "nothing_to_compare" in codes[2]
    assert 3 not in codes
    assert "mostly_starter" in codes[4]


def test_pipeline_flags_the_copy_and_only_the_copy():
    files = {1: source("p10_sort_a"), 2: source("p10_sort_b"), 3: source("p10_sort_a__restructured"),
             4: source("p10_sort_c")}
    result = run_similarity(files, CopyClassifier.load(model_path_for("hashing")), HashingEmbedder(), 0.5)
    assert len(result.pairs) == 6 and all(p.a < p.b for p in result.pairs)
    assert [(p.a, p.b) for p in result.pairs if p.flagged] == [(1, 3)]
    assert result.clusters == [[1, 3]]


def test_canonicalize_removes_names_but_keeps_builtins():
    from codetwin.similarity.embed import canonicalize

    a = canonicalize("def area(r):\n    # circle\n    return 3.14 * r * r\nprint(area(2))\n")
    b = canonicalize("def size(radius):\n    return 3.14 * radius * radius\nprint(size(2))\n")
    assert a.split() == b.split()
    assert "print" in a and "area" not in a
