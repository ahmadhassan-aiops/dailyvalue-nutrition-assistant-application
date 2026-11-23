"""DV-01 Ask: a conversation answered live from the NIH pages, each reply an "Answer facts" panel with its sources."""

from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from label import data, ui
from nutri import pipeline
from nutri.llm import api_key

LIVE_LIMIT = 8
EXAMPLES = ["What are the symptoms of vitamin B12 deficiency?", "What foods are good sources of iron?",
            "What is metabolic syndrome?", "How can I get calcium if I'm lactose intolerant?"]
PROFILE = {
    "Age group": ["Prefer not to say", "Child", "Teenager", "Adult", "Older adult (65+)"],
    "Pregnant or breastfeeding": ["Prefer not to say", "No", "Pregnant", "Breastfeeding"],
    "Diet": ["Prefer not to say", "No restrictions", "Vegetarian", "Vegan", "Gluten-free", "Lactose-free"],
}


def _ask(question: str) -> None:
    turns = st.session_state.setdefault("turns", [])
    history = [(x["question"], x["text"]) for x in turns if x["label"] == "allowed"]
    profile = {k: st.session_state.get(f"p_{k}") for k in PROFILE}
    from nutri.llm import Client

    t = pipeline.run(Client(), data.retriever(), question, data.chosen(), history=history, profile=profile)
    turns.append({"question": question, "standalone": t.standalone, "label": t.label, "text": t.text,
                  "covered": t.answer.covered if t.answer else False,
                  "professional": t.answer.see_a_professional if t.answer else False,
                  "sentences": [s.model_dump() for s in t.answer.sentences] if t.answer else [],
                  "passages": [asdict(p) for p in t.passages], "cited": t.cited, "error": t.error})
    st.session_state["used"] = st.session_state.get("used", 0) + 1


def _turn(x: dict, i: int) -> None:
    ui.you(x["question"], x["standalone"])
    if x["label"] in pipeline.FIXED:
        st.html(ui.safety_card(x["label"], x["text"]))
        return
    if x["error"]:
        st.error(x["text"], icon=":material/error:")
        return
    a, b = st.columns([1.35, 1], gap="medium")
    a.html(ui.answer_facts(x["question"], x["sentences"], x["covered"], x["professional"], len(x["passages"])))
    with b, ui.panel(f"{i:02d}", "Sources", "menu_book", "The five passages the search found; highlighted numbers "
                     "were cited."):
        st.html(ui.sources_list(x["passages"], x["cited"]))


def render() -> None:
    ui.page("DV-01", "Ask", "Nutrition questions, answered from NIH pages",
            "Ask about vitamins, minerals, anemia, weight, digestive conditions or healthy eating. Every sentence of "
            "the answer shows which <b>MedlinePlus, NHLBI or NIDDK</b> page it comes from, and when the pages do not "
            "cover a question, DailyValue says so instead of guessing.")
    key = api_key()
    used = st.session_state.get("used", 0)
    left, right = st.columns([1, 2.6], gap="medium")
    with left:
        with ui.panel("A", "About you", "person", "Optional. The answer points out what the pages say about people "
                      "like you. Kept only for this visit."):
            for k, options in PROFILE.items():
                st.selectbox(k, options, key=f"p_{k}")
        with ui.panel("B", "This visit", "hourglass_top"):
            st.html(f'<div class="visit"><p><b>Questions left</b><span class="big">{max(LIVE_LIMIT - used, 0)}</span> of '
                    f'{LIVE_LIMIT}</p><p><b>Answer model</b>{ui.esc(data.chosen())} on Groq</p>'
                    '<p><b>Memory</b>The last 3 turns, so follow-ups work</p></div>')
            if st.session_state.get("turns"):
                if st.button("Start a new conversation", icon=":material/restart_alt:", width="stretch"):
                    st.session_state["turns"] = []
                    st.rerun()
    with right:
        turns = st.session_state.get("turns", [])
        if not turns:
            with ui.panel("01", "Try a question", "lightbulb", "Or type your own below.", main=True):
                cols = st.columns(2)
                for j, ex in enumerate(EXAMPLES):
                    if cols[j % 2].button(ex, key=f"ex{j}", width="stretch", disabled=not key or used >= LIVE_LIMIT):
                        st.session_state["pending"] = ex
                ui.caution("DailyValue gives general information, not medical advice. It does not diagnose, and it "
                           "will not suggest doses. Do not type names or other personal details.", "health_and_safety")
        for i, x in enumerate(turns, 1):
            _turn(x, i)
        if not key:
            st.info("Live answers are switched off here: no Groq key is configured. The Quality page shows the "
                    "evaluated answers.", icon=":material/key_off:")
        elif used >= LIVE_LIMIT:
            st.info(f"You have asked the {LIVE_LIMIT} questions for this visit. The Quality page shows every evaluated "
                    "answer.", icon=":material/hourglass_empty:")
    typed = st.chat_input("Ask a nutrition question", disabled=not key or used >= LIVE_LIMIT, max_chars=400)
    question = typed or st.session_state.pop("pending", None)
    if question and key and used < LIVE_LIMIT:
        done = False
        with right, st.spinner("Checking the question, searching the pages and writing the answer..."):
            try:
                _ask(question.strip())
                done = True
            except Exception as err:   # network, rate limit or provider error
                st.error(f"The model could not be reached ({type(err).__name__}). Try again in a minute.",
                         icon=":material/cloud_off:")
        if done:
            st.rerun()
    ui.footer()
