"""DV-04 Method: the pipeline, the models, the sources, the evaluation and the limits."""

from __future__ import annotations

import streamlit as st

from label import data, ui


def render() -> None:
    s = data.summary()
    ui.page("DV-04", "Method", "How an answer is made",
            "Five steps per question; only one of them writes text, and it may only use the passages in front of it.")
    a, b = st.columns([1.15, 1], gap="medium")
    with a, ui.panel("01", "One question, five steps", "account_tree", main=True):
        st.html(f"""<ol class="steps">
<li><div><b>Screen</b>{ui.esc(s['screen_model'])} reads the message against a written policy: crisis, emergency, harmful
request, attempt to change the instructions, or allowed. Anything but allowed gets a fixed, reviewed reply.</div></li>
<li><div><b>Make it standalone</b>For a follow-up, {ui.esc(s['rewrite_model'])} rewrites it using the last three turns
("How is it treated?" becomes "How is iron-deficiency anemia treated?").</div></li>
<li><div><b>Search</b>BM25 word matching and bge-small-en-v1.5 embeddings (ONNX, on CPU) each rank the passages; reciprocal
rank fusion merges them and the top {s['k']} go on.</div></li>
<li><div><b>Answer</b>{ui.esc(s['chosen'])} returns strict JSON: whether the passages cover the question, the answer as
sentences each with its source numbers, and whether to refer the person to a professional.</div></li>
<li><div><b>Check</b>Code rejects citations to passages that were not given, sentences of fact without a source and
answers that are too long or too short.</div></li></ol>""")
    with b:
        with ui.panel("02", "Stack", "layers"):
            st.html(f"""<dl class="facts">
<dt>Answers</dt><dd>{ui.esc(s['chosen'])}, open weights, on Groq's free tier</dd>
<dt>Safety screen</dt><dd>{ui.esc(s['screen_model'])} (policy-following classifier)</dd>
<dt>Embeddings</dt><dd>BAAI bge-small-en-v1.5 through fastembed (ONNX, no PyTorch)</dd>
<dt>Keyword search</dt><dd>BM25 (rank-bm25)</dd>
<dt>Index</dt><dd>358 passages in a NumPy array, searched in memory</dd>
<dt>Memory</dt><dd>This visit only: the last three turns and the optional profile</dd>
<dt>Validation</dt><dd>pydantic models behind every JSON answer</dd></dl>""")
        with ui.panel("03", "Sources", "menu_book"):
            st.html('<dl class="facts"><dt>MedlinePlus</dt><dd>Health-topic summaries written by the National Library '
                    'of Medicine, through its web service</dd><dt>NHLBI, NIDDK</dt><dd>Pages on anemia, the metabolic '
                    'syndrome, obesity, weight-loss surgery and digestive conditions, split at their headings</dd>'
                    '<dt>Licence</dt><dd>U.S. government works, public domain; credited on every answer</dd></dl>')
    with ui.panel("04", "Evaluation", "rule", "evaluate.py; every model call is cached, so the scores replay "
                  "without a key."):
        c = s["counts"]
        ui.notes(f"{c['questions']} answerable questions, each with the pages that answer it; {c['out_of_scope']} "
                 f"questions the pages do not cover; {c['safety']} safety cases with the expected label; "
                 f"{c['followups']} two-turn conversations. All written before the first run; the prompts were not "
                 "tuned on them.",
                 f"A second model ({ui.esc(s['models'][s['chosen']]['judge']['model'])}) lists every claim in an "
                 "answer that its passages do not state. It is a model too, so its verdicts are a strong signal, not "
                 "proof.",
                 "Selection rule, fixed before the runs: " + ui.esc(s["selection"]))
    with ui.panel("05", "Limits", "warning"):
        ui.notes("The pages are written for the public; detailed clinical questions (doses, lab ranges for a "
                 "specific case, drug interactions) are mostly outside them, and DailyValue says so.",
                 "Questions are screened by a model; a crisis worded in an unusual way could be missed. The fixed "
                 "replies point to emergency numbers and helplines.",
                 "Groq's free tier allows a limited number of tokens a day for every app on the key; at the limit "
                 "the live answers pause until it resets. The safety screen's model allows 2,000 tokens a minute, "
                 "about four questions a minute across all visitors; in a busy minute an answer waits.",
                 "English only. Pages were collected on the date in data/sources.jsonl and are not updated "
                 "automatically.")
    ui.footer()
