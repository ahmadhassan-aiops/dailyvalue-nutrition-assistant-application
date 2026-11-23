"""DailyValue tests: the shipped knowledge base, search, the answer checks, the safety short-circuit and every page."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from nutri import corpus, pipeline
from nutri.corpus import MAX_WORDS
from nutri.retrieve import Retriever
from nutri.schema import Answer, Screen, Sentence, strict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ALLOWED = re.compile(r"^https://(medlineplus\.gov/[a-z0-9]+\.html|www\.nhlbi\.nih\.gov/health/|www\.niddk\.nih\.gov/health-information/)")


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    return Retriever()


def test_sources_are_public_domain_government_pages():
    passages = corpus.load()
    assert len(passages) > 300
    assert all(ALLOWED.match(p.url) for p in passages)
    assert not any("/ency/" in p.url for p in passages)          # A.D.A.M. encyclopedia is copyrighted
    assert all(len(p.text.split()) <= MAX_WORDS for p in passages)


def test_index_matches_passages(retriever):
    assert retriever.vectors.shape == (len(retriever.passages), 384)


def test_search_reproduces_the_evaluation(retriever):
    s = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))["retrieval"]["hybrid"]
    import pandas as pd

    q = pd.read_csv(DATA / "questions.csv", keep_default_na=False)
    q = q[q.kind == "answer"]
    found = 0
    for row in q.itertuples():
        urls = [p.url for p, _ in retriever.search(row.question, k=pipeline.K)]
        found += any(e in u for u in urls for e in row.expected.split(";"))
    assert found == s["hit_at_5"]


def test_strict_schema_requires_every_field():
    s = strict(Answer)
    assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
    item = s["$defs"]["Sentence"]
    assert item["additionalProperties"] is False and set(item["required"]) == {"text", "sources"}


def _answer(*sentences, covered=True):
    return Answer(covered=covered, sentences=[Sentence(text=t, sources=s) for t, s in sentences],
                  see_a_professional=False)


def test_check_flags_bad_citations():
    ok = _answer(("Iron helps make hemoglobin, the protein in red blood cells that carries oxygen around the body.", [1]),
                 ("Good sources include lean meat, seafood, beans, dark green leafy vegetables and fortified cereals.", [2]),
                 ("Ask a doctor before taking iron pills.", []))
    assert pipeline.check(ok, 5) == ([1, 2], [])
    _, problems = pipeline.check(_answer(("Iron helps make hemoglobin in red blood cells for oxygen transport "
                                          "around the whole body every day.", [7])), 5)
    assert "cites a source that was not given" in problems
    _, problems = pipeline.check(_answer(("Iron helps make hemoglobin.", [1]), ("Spinach has the most iron of "
                                          "any food and fixes anemia in a week for nearly everyone.", [])), 5)
    assert any("without a source" in p for p in problems)
    assert pipeline.check(_answer(("These pages do not cover selenium.", []), covered=False), 5) == ([], [])


class FakeClient:
    """Answers the screen with a fixed label; fails the test if anything after the screen is called."""

    def __init__(self, label: str):
        self.label = label

    def structured(self, model, system, user, schema, parse, tag="", max_tokens=900):
        assert tag == "screen", f"{tag} called after a {self.label} screen"
        call = type("C", (), {"prompt_tokens": 1, "completion_tokens": 1, "seconds": 0.0})()
        return Screen(label=self.label, reason="test"), call, ""


@pytest.mark.parametrize("label", ["crisis", "emergency", "harmful", "manipulation"])
def test_screened_messages_get_the_fixed_reply(label, retriever):
    t = pipeline.run(FakeClient(label), retriever, "message", "any-model")
    assert t.label == label and t.text == pipeline.FIXED[label] and not t.passages


def run(module: str) -> AppTest:
    script = f"""
import importlib
from label.ui import inject_css
inject_css()
importlib.import_module("views.{module}").render()
"""
    return AppTest.from_string(script, default_timeout=120).run()


@pytest.mark.parametrize("page", ["ask", "shelf", "quality", "method"])
def test_every_page_renders(page):
    at = run(page)
    assert not at.exception, at.exception


def test_ask_without_a_key_explains_itself(monkeypatch):
    import views.ask

    monkeypatch.setattr(views.ask, "api_key", lambda: None)
    at = run("ask")
    assert not at.exception and any("switched off" in i.value for i in at.info)


def test_quality_shows_every_kind_of_question():
    at = run("quality")
    for kind in ["Outside the pages", "Safety", "Follow-up"]:
        at.segmented_control(key="q_kind").set_value(kind).run()
        assert not at.exception, (kind, at.exception)
