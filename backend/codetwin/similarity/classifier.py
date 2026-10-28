"""Step 4: the trained logistic regression that turns two scores into a copy probability.

The model is stored as plain JSON (two weights and an intercept), not a
pickle: it is easy to explain and safe to load. ml/train.py writes it.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "models"


@dataclass(frozen=True)
class CopyClassifier:
    version: str            # stored on every run as model_version
    embedder: str
    w_fingerprint: float
    w_embedding: float
    intercept: float
    threshold: float        # recommended default; a run may override it

    def probability(self, fingerprint_score: float, embedding_score: float) -> float:
        z = self.intercept + self.w_fingerprint * fingerprint_score + self.w_embedding * embedding_score
        return 1.0 / (1.0 + math.exp(-z))

    @classmethod
    def load(cls, path: Path) -> "CopyClassifier":
        d = json.loads(Path(path).read_text())
        return cls(d["version"], d["embedder"], d["coef"][0], d["coef"][1], d["intercept"], d["threshold"])


def model_path_for(embedder: str) -> Path:
    return MODELS_DIR / f"{embedder}.json"
