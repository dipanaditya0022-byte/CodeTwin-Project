"""Step 4: the trained logistic regression that turns the similarity scores into a copy probability.

The model is stored as plain JSON (one weight per score and an intercept), not a pickle: it is easy
to explain and safe to load. ml/train.py writes it. A model names the scores it uses:
  * fingerprint_score   Jaccard share of winnowed fingerprints
  * embedding_score     cosine similarity of the two embeddings
  * containment_score   share of the smaller file's fingerprints found in the other (newer models)
Older two-score models keep working unchanged.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "models"

FEATURES = ("fingerprint_score", "embedding_score", "containment_score")
LABELS = {
    "fingerprint_score": "Shared code fragments (fingerprints)",
    "embedding_score": "Similar structure (embedding)",
    "containment_score": "Share of the smaller file found in the other",
}


@dataclass(frozen=True)
class CopyClassifier:
    version: str            # stored on every run as model_version
    embedder: str
    features: tuple[str, ...]
    weights: tuple[float, ...]
    intercept: float
    threshold: float        # recommended default; a run may override it
    operating_points: tuple = field(default=())   # measured precision/recall per threshold, from training

    @property
    def uses_containment(self) -> bool:
        return "containment_score" in self.features

    def _z(self, scores: dict[str, float]) -> float:
        return self.intercept + sum(w * scores[f] for f, w in zip(self.features, self.weights))

    def probability(self, fingerprint_score: float, embedding_score: float,
                    containment_score: float | None = None) -> float:
        scores = {"fingerprint_score": fingerprint_score, "embedding_score": embedding_score,
                  "containment_score": containment_score}
        if self.uses_containment and containment_score is None:
            raise ValueError(f"model {self.version} needs the containment score")
        return 1.0 / (1.0 + math.exp(-self._z(scores)))

    def explain(self, scores: dict[str, float | None]) -> dict:
        """How each score moved this pair's probability: weight × score, on the log-odds scale.

        The parts add up (with the intercept) to the log-odds the probability comes from, so the
        largest part is the score that did most to flag (or clear) the pair.
        """
        parts = [{"feature": f, "label": LABELS[f], "score": round(float(scores[f]), 4), "weight": w,
                  "contribution": round(w * float(scores[f]), 3)} for f, w in zip(self.features, self.weights)]
        z = self.intercept + sum(p["contribution"] for p in parts)
        return {"model_version": self.version, "intercept": self.intercept, "parts": parts,
                "log_odds": round(z, 3), "probability": round(1.0 / (1.0 + math.exp(-z)), 4),
                "main_reason": max(parts, key=lambda p: p["contribution"])["label"]}

    @classmethod
    def load(cls, path: Path) -> "CopyClassifier":
        d = json.loads(Path(path).read_text())
        features = tuple(d.get("features", FEATURES[:2]))
        unknown = set(features) - set(FEATURES)
        if unknown or len(features) != len(d["coef"]):
            raise ValueError(f"model {path} has features {features} that this code cannot compute")
        return cls(d["version"], d["embedder"], features, tuple(d["coef"]), d["intercept"], d["threshold"],
                   tuple(d.get("operating_points", ())))


def model_path_for(embedder: str) -> Path:
    return MODELS_DIR / f"{embedder}.json"


def classifier_for_version(version: str) -> CopyClassifier | None:
    """The stored model with this version, so an older run can still be explained. None if it is gone.

    Retired models are kept in models/archive/ for exactly this; a new run always uses the current one.
    """
    for path in sorted(MODELS_DIR.rglob("*.json")):
        try:
            model = CopyClassifier.load(path)
        except (ValueError, KeyError):
            continue
        if model.version == version:
            return model
    return None
