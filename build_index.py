"""Splits data/sources.jsonl into passages and embeds them: writes data/passages.json and data/vectors.npy."""

import numpy as np

from nutri import corpus
from nutri.retrieve import Embedder


def main() -> None:
    passages = corpus.build()
    corpus.save(passages)
    vectors = Embedder().passages([p.searchable for p in passages])
    np.save(corpus.DATA / "vectors.npy", vectors.astype(np.float16))
    words = [len(p.text.split()) for p in passages]
    print(f"{len(passages)} passages, median {int(np.median(words))} words, max {max(words)}; vectors {vectors.shape}")


if __name__ == "__main__":
    main()
