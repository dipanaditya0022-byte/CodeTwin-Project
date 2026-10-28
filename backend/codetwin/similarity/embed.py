"""Step 3: turn each file into a vector; the embedding score is cosine similarity.

Two embedders share one interface:

* "unixcoder" - microsoft/unixcoder-base, a pretrained open-source code
  model run inside the worker (needs torch and transformers; about 500 MB
  of weights downloaded once). Student code never leaves the tenant.
  Identifiers are canonicalised (v1, v2, ...) before embedding: on raw
  code the vectors follow variable names, and a renamed copy scored no
  higher than an independent solution (see docs/REPORT.md, section 6).
* "hashing"   - a bag of normalised token 1-3-grams hashed into a fixed
  vector. No download and no GPU; it catches statement reordering, which
  the order-sensitive fingerprint misses, but it is not a learned model.
  It is the default for local development and tests.

The classifier is trained separately for each embedder because their
score distributions differ.
"""
from __future__ import annotations

import builtins
import io
import keyword
import tokenize
from functools import lru_cache

import numpy as np

from .normalize import normalize


class HashingEmbedder:
    name = "hashing-ngram"

    def __init__(self, n_features: int = 2 ** 16):
        from sklearn.feature_extraction.text import HashingVectorizer

        self.vectorizer = HashingVectorizer(analyzer=self._ngrams, n_features=n_features,
                                            alternate_sign=False, norm=None)

    @staticmethod
    def _ngrams(source: str) -> list[str]:
        texts = [t.text for t in normalize(source)]
        grams = list(texts)
        for n in (2, 3):
            grams += [" ".join(texts[i:i + n]) for i in range(len(texts) - n + 1)]
        return grams

    def embed(self, sources: list[str]) -> np.ndarray:
        from sklearn.preprocessing import normalize as l2

        x = self.vectorizer.transform(sources)
        x.data = np.log1p(x.data)          # damp very frequent n-grams
        return l2(x).toarray().astype(np.float32)


_BUILTINS = set(dir(builtins))


def canonicalize(source: str) -> str:
    """Rename identifiers to v1, v2, ... in order of first use and drop comments.
    Keywords and builtins (print, len, range) are kept; every other name is renamed."""
    names: dict[str, str] = {}
    out = []
    try:
        for t in tokenize.generate_tokens(io.StringIO(source).readline):
            text = t.string
            if t.type == tokenize.NAME and not keyword.iskeyword(text) and text not in _BUILTINS:
                text = names.setdefault(text, f"v{len(names) + 1}")
            elif t.type == tokenize.COMMENT:
                text = ""
            out.append((t.type, text))
        return tokenize.untokenize(out)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return source


class UnixcoderEmbedder:
    name = "unixcoder-canon"
    MODEL = "microsoft/unixcoder-base"
    WINDOW = 509   # 512 minus [CLS] <encoder-only> [SEP] ... [SEP]

    def __init__(self):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL)
        self.model = AutoModel.from_pretrained(self.MODEL).eval()

    def _embed_one(self, source: str) -> np.ndarray:
        ids = self.tokenizer(source, add_special_tokens=False)["input_ids"] or [self.tokenizer.unk_token_id]
        chunks = [ids[i:i + self.WINDOW] for i in range(0, len(ids), self.WINDOW)]
        # UniXcoder's input format for encoder-only use: [CLS] <encoder-only> [SEP] code [SEP]
        prefix = [self.tokenizer.cls_token_id, self.tokenizer.convert_tokens_to_ids("<encoder-only>"),
                  self.tokenizer.sep_token_id]
        vectors = []
        with self.torch.no_grad():
            for chunk in chunks:   # long files are embedded in windows and averaged
                x = self.torch.tensor([prefix + chunk + [self.tokenizer.sep_token_id]])
                hidden = self.model(x).last_hidden_state[0]
                vectors.append(hidden.mean(dim=0).numpy())
        v = np.mean(vectors, axis=0)
        return v / (np.linalg.norm(v) or 1.0)

    def embed(self, sources: list[str]) -> np.ndarray:
        return np.stack([self._embed_one(canonicalize(s)) for s in sources]).astype(np.float32)


@lru_cache
def get_embedder(name: str):
    if name == "unixcoder":
        return UnixcoderEmbedder()
    if name == "hashing":
        return HashingEmbedder()
    raise ValueError(f"unknown embedder {name!r}")


def cosine_matrix(vectors: np.ndarray) -> np.ndarray:
    """Pairwise cosine similarity of L2-normalised rows, clipped to [0, 1]."""
    return np.clip(vectors @ vectors.T, 0.0, 1.0)
