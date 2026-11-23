"""Hybrid search: BM25 on words plus bge-small embeddings, merged by reciprocal rank fusion."""

from __future__ import annotations

import re
from functools import cached_property

import numpy as np
from rank_bm25 import BM25Okapi

from .corpus import DATA, Passage, load

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
STOP = set("a an and are as at be by can do does for from how i if in is it its me my of on or should so that the "
           "their them there these this to was what when where which who why will with you your".split())


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


class Embedder:
    """fastembed's ONNX build of bge-small (CPU, no PyTorch). Queries get bge's retrieval instruction."""

    def __init__(self, model: str = EMBED_MODEL):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model)

    def passages(self, texts: list[str]) -> np.ndarray:
        return np.array(list(self.model.passage_embed(texts)), dtype=np.float32)

    def query(self, text: str) -> np.ndarray:
        return np.array(next(iter(self.model.query_embed(text))), dtype=np.float32)


class Retriever:
    def __init__(self, passages: list[Passage] | None = None, vectors: np.ndarray | None = None, embedder=None):
        self.passages = passages if passages is not None else load()
        self.vectors = vectors if vectors is not None else np.load(DATA / "vectors.npy").astype(np.float32)
        self._embedder = embedder
        self.bm25 = BM25Okapi([tokens(p.searchable) for p in self.passages])

    @cached_property
    def embedder(self) -> Embedder:
        return self._embedder or Embedder()

    def bm25_rank(self, query: str) -> np.ndarray:
        return np.argsort(-self.bm25.get_scores(tokens(query)), kind="stable")

    def dense_rank(self, query: str) -> np.ndarray:
        return np.argsort(-(self.vectors @ self.embedder.query(query)), kind="stable")

    def search(self, query: str, k: int = 5, mode: str = "hybrid", rrf_k: int = 60) -> list[tuple[Passage, float]]:
        if mode == "bm25":
            order = self.bm25_rank(query)
            return [(self.passages[i], 0.0) for i in order[:k]]
        if mode == "dense":
            order = self.dense_rank(query)
            return [(self.passages[i], 0.0) for i in order[:k]]
        fused = np.zeros(len(self.passages))
        for order in (self.bm25_rank(query), self.dense_rank(query)):
            fused[order] += 1.0 / (rrf_k + np.arange(1, len(order) + 1))
        best = np.argsort(-fused, kind="stable")[:k]
        return [(self.passages[i], float(fused[i])) for i in best]
