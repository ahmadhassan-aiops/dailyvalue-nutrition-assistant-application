"""Cached loaders: the evaluation results and the search index that ship with the app."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from nutri.retrieve import Retriever

DATA = Path(__file__).resolve().parents[1] / "data"


@st.cache_data
def summary() -> dict:
    return json.loads((DATA / "summary.json").read_text(encoding="utf-8"))


@st.cache_data
def runs(model: str) -> list[dict]:
    return json.loads((DATA / "runs" / f"{model.replace('/', '_')}.json").read_text(encoding="utf-8"))


@st.cache_data
def questions() -> pd.DataFrame:
    return pd.read_csv(DATA / "questions.csv", keep_default_na=False)


@st.cache_data
def pages() -> pd.DataFrame:
    """One row per source page (the NIH pages were stored per section)."""
    rows = [json.loads(line) for line in (DATA / "sources.jsonl").read_text(encoding="utf-8").splitlines()]
    df = pd.DataFrame(rows)
    df["page"] = df["title"].str.split(": ").str[0]
    df["words"] = df["text"].str.split().str.len()
    df["org"] = df["source"].str.split(",").str[0]
    return (df.groupby(["url", "org"], sort=False).agg(page=("page", "first"), sections=("title", "size"),
                                                       words=("words", "sum")).reset_index())


@st.cache_resource(show_spinner="Loading the search index...")
def retriever() -> Retriever:
    return Retriever()


def chosen() -> str:
    return summary()["chosen"]
