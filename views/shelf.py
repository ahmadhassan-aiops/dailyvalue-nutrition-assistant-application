"""DV-02 Shelf: the pages DailyValue answers from, and the search that picks passages for an answer (no model)."""

from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from label import data, ui


def render() -> None:
    pg = data.pages()
    r = data.retriever()
    words = int(pg["words"].sum())
    ui.page("DV-02", "Shelf", "What DailyValue reads from",
            f"<b>{len(pg)} public-domain pages</b> from the U.S. National Institutes of Health, split into "
            f"{len(r.passages)} short passages. An answer may use only the five passages the search returns.")
    by = pg.groupby("org").agg(n=("url", "size"), w=("words", "sum"))
    ui.tiles([("Pages", str(len(pg)), "health topics and sections"),
              ("Passages", str(len(r.passages)), "up to 220 words each"),
              ("Words", f"{words:,}", "all public domain"),
              ("MedlinePlus", str(by.loc["MedlinePlus", "n"]), "topic summaries (NLM)"),
              ("NHLBI + NIDDK", str(by.drop("MedlinePlus")["n"].sum()), "detailed pages (NIH)")], highlight=0)

    with ui.panel("01", "Search the shelf", "search", "The same search the answers use: word matching (BM25) and "
                  "meaning (bge-small embeddings), merged. Runs here without a language model.", main=True):
        q = st.text_input("Search", value="vitamin B12 for vegans", key="s_q", max_chars=200)
        mode = st.segmented_control("Search by", ["Hybrid", "Words (BM25)", "Meaning (embeddings)"], key="s_mode",
                                    default="Hybrid")
        if q.strip():
            m = {"Hybrid": "hybrid", "Words (BM25)": "bm25", "Meaning (embeddings)": "dense"}[mode or "Hybrid"]
            hits = [asdict(p) for p, _ in r.search(q, k=5, mode=m)]
            st.html(ui.sources_list(hits, []))

    with ui.panel("02", "Every page", "menu_book", "Collected through the MedlinePlus web service and from NHLBI and "
                  "NIDDK pages by build_corpus.py; copyrighted encyclopedia articles are never used."):
        rows = "".join(f'<tr><td>{ui.org(o)}<a href="{ui.esc(u)}" target="_blank">{ui.esc(p)}</a></td>'
                       f'<td class="n">{s}</td><td class="n">{w:,}</td></tr>'
                       for u, o, p, s, w in pg[["url", "org", "page", "sections", "words"]].itertuples(index=False))
        st.html('<table class="tbl"><thead><tr><th>Page</th><th class="n">Sections</th><th class="n">Words</th></tr>'
                f'</thead><tbody>{rows}</tbody></table>')
        ui.notes("MedlinePlus summaries are short overviews; the NHLBI and NIDDK pages add detail on anemia, the "
                 "metabolic syndrome, obesity, weight-loss surgery, celiac disease, lactose intolerance, iron overload "
                 "and short bowel syndrome.",
                 "Topics outside these pages (for example selenium, sports nutrition or calorie counts of foods) "
                 "are answered with \"not in these sources\".")
    ui.footer()
