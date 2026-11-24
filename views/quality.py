"""DV-03 Quality: search accuracy, answers checked against their sources, questions outside the pages, safety."""

from __future__ import annotations

import streamlit as st

from label import data, ui
from nutri import pipeline

MODES = {"bm25": "Words (BM25)", "dense": "Meaning (bge-small embeddings)", "hybrid": "Hybrid (both, rank fusion)"}


def _model_table(s: dict) -> str:
    rows = ""
    for m, v in s["models"].items():
        partial = v["answered"] < v["of"] or v["judge"]["judged"] < v["covered_rows"]
        rows += (f'<tr class="{"pick" if m == s["chosen"] else ""}"><td>{ui.esc(m)}'
                 f'{" (chosen)" if m == s["chosen"] else ""}{" (partial)" if partial else ""}</td>'
                 f'<td class="n">{ui.pct(v["judge"]["fully_supported"])}</td>'
                 f'<td class="n">{ui.pct(v["answerable"]["covered"])}</td>'
                 f'<td class="n">{ui.pct(v["out_of_scope"]["declined"])}</td>'
                 f'<td class="n">{ui.pct(v["safety"]["label_right"])}</td>'
                 f'<td class="n">{ui.pct(v["answerable"]["checks_pass"])}</td>'
                 f'<td class="n">{v.get("answer_seconds", {}).get("median_seconds", v["median_seconds"])} s</td><td class="n">{v["mean_tokens"]:,}</td></tr>')
    return ('<table class="tbl"><thead><tr><th>Answer model</th><th class="n">Fully supported</th>'
            '<th class="n">Answerable answered</th><th class="n">Outside declined</th><th class="n">Safety label right</th>'
            '<th class="n">Checks pass</th><th class="n">Answer time (median)</th><th class="n">Tokens</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')


def render() -> None:
    s = data.summary()
    m = s["models"][s["chosen"]]
    rt = s["retrieval"]["hybrid"]
    c = s["counts"]
    ui.page("DV-03", "Quality", "How far the answers can be trusted",
            f"{c['questions']} answerable questions, {c['out_of_scope']} the pages do not cover, {c['safety']} safety "
            f"cases and {c['followups']} follow-up conversations, all written before the first run. Every answer was "
            f"read against its sources by a second model ({ui.esc(m['judge']['model'])}).")
    ui.tiles([("Right page found", f"{rt['hit_at_5']}/{rt['n']}", "in the top 5 passages (hybrid search)"),
              ("Answers fully supported", ui.pct(m["judge"]["fully_supported"]),
               f"{m['judge']['judged']} answers read against their sources"),
              ("Answerable answered", ui.pct(m["answerable"]["covered"]), f"of {m['answerable']['n']} questions"),
              ("Outside declined", ui.pct(m["out_of_scope"]["declined"]), f"of {m['out_of_scope']['n']} questions"),
              ("Safety cases caught", ui.pct(m["safety"]["caught"]), f"of {m['safety']['n']}; label right "
               f"{ui.pct(m['safety']['label_right'])}")], highlight=1)

    with ui.panel("01", "Answer models", "leaderboard", ui.esc(s["selection"]), main=True):
        st.html(_model_table(s))
        if len(s.get("complete", [])) < len(s["models"]):
            ui.caution("A partial run stopped at Groq's free daily token limit; it is shown for comparison and was "
                       "not eligible to be chosen.", "hourglass_bottom")

    a, b = st.columns(2, gap="medium")
    with a, ui.panel("02", "Search", "search", "Is a page that answers the question among the passages the model "
                     "sees? Pages were listed for each question before any search was run."):
        rows = "".join(f'<tr class="{"pick" if k == "hybrid" else ""}"><td>{v}</td>'
                       f'<td class="n">{s["retrieval"][k]["hit_at_1"]}/{s["retrieval"][k]["n"]}</td>'
                       f'<td class="n">{s["retrieval"][k]["hit_at_5"]}/{s["retrieval"][k]["n"]}</td>'
                       f'<td class="n">{s["retrieval"][k]["mrr_at_10"]:.3f}</td></tr>' for k, v in MODES.items())
        st.html('<table class="tbl"><thead><tr><th>Search</th><th class="n">First hit</th><th class="n">In top 5</th>'
                f'<th class="n">MRR@10</th></tr></thead><tbody>{rows}</tbody></table>')
        ui.notes(f"Follow-ups such as \"How is it treated?\" find the right page {s['retrieval']['followups_unrewritten']} "
                 f"of {c['followups']} times as typed; DailyValue first rewrites them into a standalone question "
                 f"({ui.esc(s['rewrite_model'])}), and then finds it {ui.pct(m['followups']['right_page'])} of the time.")
    with b, ui.panel("03", "Safety cases", "health_and_safety", f"Screened by {ui.esc(s['screen_model'])} with a "
                     "written policy before any search. A caught message gets a fixed reply, never a generated one."):
        q = data.questions().set_index("qid")
        rows = "".join(f'<tr><td>{ui.esc(q.loc[k, "question"])}</td><td>{ui.esc(q.loc[k, "expected"])}</td>'
                       f'<td class="{"ok" if v == q.loc[k, "expected"] else ("no" if v == "allowed" else "")}">'
                       f'{ui.esc(v)}</td></tr>' for k, v in m["safety"]["labels"].items())
        st.html('<table class="tbl"><thead><tr><th>Message</th><th>Expected</th><th>Labelled</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>')

    with ui.panel("04", "Every evaluated answer", "fact_check", "Pick a question to see the answer, its sources and "
                  "what the checker found."):
        rows = [x for x in data.runs(s["chosen"]) if x.get("answered")]
        kinds = {"answer": "Answerable", "out_of_scope": "Outside the pages", "safety": "Safety", "followup": "Follow-up"}
        kind = st.segmented_control("Questions", list(kinds.values()), default="Answerable", key="q_kind")
        pick = [x for x in rows if kinds[x["kind"]] == (kind or "Answerable")]
        if pick:
            x = st.selectbox("Question", pick, format_func=lambda x: f'{x["qid"]}  ·  {x["question"]}', key="q_pick")
            if x["label"] in pipeline.FIXED:
                st.html(ui.safety_card(x["label"], x["text"]))
            else:
                passages = [{"title": t, "url": u, "text": tx, "source": "MedlinePlus" if "medlineplus" in u else
                             ("NHLBI" if "nhlbi" in u else "NIDDK")} for t, u, tx in zip(x["titles"], x["urls"], x["texts"])]
                l, r = st.columns([1.35, 1], gap="medium")
                l.html(ui.answer_facts(x["question"], x["sentences"], bool(x["covered"]), bool(x["see_a_professional"]),
                                       len(passages), x["standalone"]))
                if x.get("judged"):
                    bad = x["unsupported"]
                    l.html(f'<div class="caution">{ui.icon("fact_check")}<div><b>Checker:</b> '
                           + ("every statement is in the sources." if not bad else
                              "not in the sources: " + "; ".join(ui.esc(b) for b in bad))
                           + ("" if x["answers_question"] else " It also judged that the reply does not answer the question.")
                           + "</div></div>")
                r.html(ui.sources_list(passages, sorted({c for st_ in x["sentences"] for c in st_["sources"]})))
    ui.footer()
