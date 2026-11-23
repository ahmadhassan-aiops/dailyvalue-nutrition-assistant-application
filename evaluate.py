"""Evaluates DailyValue on the hand-written questions in data/ (written before any run).

    python evaluate.py --retrieval              # search only: BM25, embeddings, hybrid (free, no key)
    python evaluate.py --collect MODEL          # answer every question with MODEL (fills data/cache/)
    python evaluate.py --judge MODEL            # check MODEL's answers against their sources (gpt-oss-20b judges)
    python evaluate.py                          # score everything already collected -> data/summary.json

Every call is cached in data/cache/<model>.jsonl, so scoring replays for free. Once Groq's daily token limit is
reached the remaining questions are left unanswered (and reported as such) and can be completed another day.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import pandas as pd

from nutri import pipeline
from nutri.llm import Client
from nutri.retrieve import Retriever

DATA = Path(__file__).parent / "data"
JUDGE_MODEL = "openai/gpt-oss-20b"


def questions() -> pd.DataFrame:
    return pd.read_csv(DATA / "questions.csv", keep_default_na=False)


def followups() -> pd.DataFrame:
    return pd.read_csv(DATA / "followups.csv", keep_default_na=False)


def client_for(model: str) -> Client:
    return Client(cache=DATA / "cache" / f"{model.replace('/', '_')}.jsonl")


class Shared(Client):
    """One client whose cache file follows the model of each call (answers, screens, rewrites and judgements all
    land in their own model's file)."""

    def __init__(self):
        super().__init__()
        self.clients: dict[str, Client] = {}

    def complete(self, model, *a, **kw):
        if model not in self.clients:
            self.clients[model] = client_for(model)
        return self.clients[model].complete(model, *a, **kw)


def hits(urls: list[str], expected: str) -> list[int]:
    exp = [e for e in expected.split(";") if e]
    return [i for i, u in enumerate(urls) if any(e in u for e in exp)]


def retrieval(r: Retriever) -> dict:
    q = questions()
    q = q[q.kind == "answer"]
    f = followups()
    out = {}
    for mode in ("bm25", "dense", "hybrid"):
        ranks, missed = [], []
        for row in q.itertuples():
            h = hits([p.url for p, _ in r.search(row.question, k=10, mode=mode)], row.expected)
            ranks.append(h[0] + 1 if h else None)
            if not h or h[0] >= pipeline.K:
                missed.append(row.qid)
        out[mode] = {"n": len(q), "hit_at_1": sum(x == 1 for x in ranks), "hit_at_5": sum(bool(x) and x <= 5 for x in ranks),
                     "mrr_at_10": round(sum(1 / x for x in ranks if x) / len(ranks), 3), "missed_at_5": missed}
    # Follow-ups searched as typed (no rewriting): how often the bare follow-up still finds the right page.
    out["followups_unrewritten"] = sum(bool(h) and h[0] < pipeline.K for h in
                                       (hits([p.url for p, _ in r.search(x.follow_up, k=10)], x.expected)
                                        for x in f.itertuples()))
    return out


def collect(model: str, r: Retriever) -> list[dict]:
    """Answers every question (one fresh conversation each) and every follow-up pair."""
    from groq import RateLimitError

    client = Shared()
    rows, limited = [], False
    items = [(x.qid, x.kind, x.question, x.expected, []) for x in questions().itertuples()]
    for x in followups().itertuples():
        items.append((x.fid, "followup", x.follow_up, x.expected, [x.first]))
    for qid, kind, question, expected, before in items:
        if limited:
            rows.append({"qid": qid, "kind": kind, "answered": False})
            continue
        try:
            history = []
            for first in before:      # the first turn of a follow-up pair, answered the same way
                t0 = pipeline.run(client, r, first, model)
                history.append((first, t0.text))
            t = pipeline.run(client, r, question, model, history=history)
        except RateLimitError:
            limited = True
            rows.append({"qid": qid, "kind": kind, "answered": False})
            continue
        rows.append({"qid": qid, "kind": kind, "answered": True, "question": question, "expected": expected,
                     "label": t.label, "standalone": t.standalone, "urls": [p.url for p in t.passages],
                     "titles": [p.title for p in t.passages], "texts": [p.text for p in t.passages],
                     "covered": t.answer.covered if t.answer else None,
                     "see_a_professional": t.answer.see_a_professional if t.answer else None,
                     "sentences": [s.model_dump() for s in t.answer.sentences] if t.answer else [],
                     "text": t.text, "problems": t.problems, "error": t.error, "tokens": t.tokens,
                     "seconds": t.seconds})
    return rows


def judge_rows(rows: list[dict], r: Retriever) -> list[dict]:
    """The judge reads each covered answer with its sources; stops at the daily limit."""
    from groq import RateLimitError

    client = client_for(JUDGE_MODEL)
    by_url = {}
    for p in r.passages:
        by_url.setdefault((p.url, p.text), p)
    for row in rows:
        row.setdefault("judged", False)
        if not row.get("answered") or not row.get("covered"):
            continue
        turn = pipeline.Turn(row["question"], text=row["text"],
                             passages=[by_url[(u, t)] for u, t in zip(row["urls"], row["texts"])])
        try:
            j = pipeline.judge(client, JUDGE_MODEL, turn)
        except RateLimitError:
            break
        if j:
            row.update(judged=True, unsupported=j.unsupported, answers_question=j.answers_question)
    return rows


def score(rows: list[dict]) -> dict:
    done = [x for x in rows if x.get("answered")]
    a = [x for x in done if x["kind"] == "answer"]
    o = [x for x in done if x["kind"] == "out_of_scope"]
    s = [x for x in done if x["kind"] == "safety"]
    f = [x for x in done if x["kind"] == "followup"]
    judged = [x for x in done if x.get("judged")]
    pct = lambda n, d: round(n / d, 3) if d else None  # noqa: E731
    return {
        "answered": len(done), "of": len(rows),
        "covered_rows": sum(bool(x.get("covered")) for x in done),
        "answerable": {"n": len(a), "covered": pct(sum(bool(x["covered"]) for x in a), len(a)),
                       "screened_out": sum(x["label"] != "allowed" for x in a),
                       "right_page_retrieved": pct(sum(bool(hits(x["urls"], x["expected"])) for x in a), len(a)),
                       "checks_pass": pct(sum(x["covered"] and not x["problems"] for x in a), len(a))},
        "out_of_scope": {"n": len(o), "declined": pct(sum(x["label"] != "allowed" or x["covered"] is False for x in o), len(o)),
                         "answered_anyway": [x["qid"] for x in o if x["label"] == "allowed" and x["covered"]]},
        "safety": {"n": len(s), "label_right": pct(sum(x["label"] == x["expected"] for x in s), len(s)),
                   "caught": pct(sum(x["label"] != "allowed" for x in s), len(s)),
                   "labels": {x["qid"]: x["label"] for x in s}},
        "followups": {"n": len(f), "right_page": pct(sum(bool(hits(x["urls"], x["expected"])) for x in f), len(f)),
                      "covered": pct(sum(bool(x["covered"]) for x in f), len(f))},
        "judge": {"model": JUDGE_MODEL, "judged": len(judged),
                  "fully_supported": pct(sum(not x["unsupported"] for x in judged), len(judged)),
                  "answers_question": pct(sum(bool(x["answers_question"]) for x in judged), len(judged)),
                  "unsupported_claims": sum(len(x["unsupported"]) for x in judged)},
        "median_seconds": round(statistics.median([x["seconds"] for x in done if x["seconds"]] or [0]), 2),
        "mean_tokens": int(statistics.mean([x["tokens"] for x in done] or [0])),
    }


def choose(models: dict[str, dict]) -> str:
    """Among models that answered every question: the most answers fully supported by their sources, then the most
    safety messages labelled right, then the most answerable questions answered, then the most out-of-scope questions
    declined, then the fastest."""
    return max(models, key=lambda m: (models[m]["judge"]["fully_supported"] or 0, models[m]["safety"]["label_right"] or 0,
                                      models[m]["answerable"]["covered"] or 0, models[m]["out_of_scope"]["declined"] or 0,
                                      -models[m]["median_seconds"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrieval", action="store_true")
    ap.add_argument("--collect")
    ap.add_argument("--judge")
    args = ap.parse_args()
    r = Retriever()
    if args.retrieval:
        print(json.dumps(retrieval(r), indent=1))
        return
    models = [args.collect] if args.collect else [args.judge] if args.judge else pipeline.ANSWER_MODELS
    summary = {"retrieval": retrieval(r), "models": {}}
    for m in models:
        rows = collect(m, r)
        if args.judge or not args.collect:
            rows = judge_rows(rows, r)
        (DATA / "runs").mkdir(exist_ok=True)
        (DATA / "runs" / f"{m.replace('/', '_')}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                                                                    encoding="utf-8")
        summary["models"][m] = score(rows)
        print(m, json.dumps(summary["models"][m], indent=1))
    if not (args.collect or args.judge):
        complete = {m: v for m, v in summary["models"].items()
                    if v["answered"] == v["of"] and v["judge"]["judged"] == v["covered_rows"]}
        summary["complete"] = sorted(complete)
        summary["chosen"] = choose(complete) if complete else pipeline.ANSWER_MODELS[0]
        summary["selection"] = " ".join(choose.__doc__.split())
        summary["screen_model"], summary["rewrite_model"], summary["k"] = (pipeline.SCREEN_MODEL,
                                                                           pipeline.REWRITE_MODEL, pipeline.K)
        summary["counts"] = {"questions": int((questions().kind == "answer").sum()),
                             "out_of_scope": int((questions().kind == "out_of_scope").sum()),
                             "safety": int((questions().kind == "safety").sum()), "followups": len(followups())}
        (DATA / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
        print("chosen:", summary["chosen"], "| complete:", summary["complete"])


if __name__ == "__main__":
    main()
