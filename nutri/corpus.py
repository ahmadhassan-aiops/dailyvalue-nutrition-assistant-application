"""Passages: the source pages split into short, titled pieces that one search hit can carry on its own."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
MAX_WORDS = 220


@dataclass(frozen=True)
class Passage:
    pid: str
    title: str
    url: str
    source: str
    text: str

    @property
    def searchable(self) -> str:
        return f"{self.title}\n{self.text}"


def _pieces(text: str, limit: int = MAX_WORDS) -> list[str]:
    """Splits at paragraph or list boundaries into pieces of at most `limit` words (a longer paragraph is split at
    sentence ends)."""
    blocks = [b.strip() for b in re.split(r"\n(?=\S)", text) if b.strip()]
    units: list[str] = []
    for b in blocks:
        if len(b.split()) <= limit:
            units.append(b)
        else:
            units += [s for s in re.split(r"(?<=[.!?])\s+", b) if s]
    out, cur = [], []
    for u in units:
        if cur and len(" ".join(cur + [u]).split()) > limit:
            out.append("\n".join(cur))
            cur = []
        cur.append(u)
    if cur:
        out.append("\n".join(cur))
    return out


def build(path: Path = DATA / "sources.jsonl") -> list[Passage]:
    passages = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        r = json.loads(line)
        title = r["title"] + (f" (also called {', '.join(r['also_called'][:3])})" if r.get("also_called") else "")
        for k, piece in enumerate(_pieces(r["text"])):
            passages.append(Passage(f"{n:03d}-{k}", title, r["url"], r["source"], piece))
    return passages


def save(passages: list[Passage], path: Path = DATA / "passages.json") -> None:
    path.write_text(json.dumps([asdict(p) for p in passages], ensure_ascii=False, indent=0), encoding="utf-8")


def load(path: Path = DATA / "passages.json") -> list[Passage]:
    return [Passage(**p) for p in json.loads(path.read_text(encoding="utf-8"))]
