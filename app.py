"""
DailyValue: nutrition questions answered only from public-domain NIH pages (MedlinePlus, NHLBI, NIDDK), every sentence
with its source. Open models on Groq answer; the search runs locally. Evaluated in evaluate.py, code in nutri/.
"""

import streamlit as st

st.set_page_config(page_title="DailyValue | Nutrition answers from NIH pages | Ahmad Hassan",
                   page_icon=":material/nutrition:", layout="wide", initial_sidebar_state="collapsed")

from label.ui import icon, inject_css  # noqa: E402
from nav import PAGES  # noqa: E402

inject_css()
current = st.navigation(PAGES, position="hidden")
cols = st.columns([2.6, 1, 1, 1, 1], vertical_alignment="bottom")
cols[0].html(f'<div class="brand"><span class="mk">{icon("nutrition")}</span><div><p class="name">DailyValue</p>'
             '<p class="tagline">Nutrition answers from NIH pages, every sentence sourced</p></div></div>')
for col, p in zip(cols[1:], PAGES):
    col.page_link(p, label=p.title, icon=p.icon, width="stretch")
k = [p.title for p in PAGES].index(current.title) + 2
st.html(f'<style>[data-testid="stHorizontalBlock"]:has(.brand) > [data-testid="stColumn"]:nth-child({k}) a '
        '{ background: #141414 !important; } '
        f'[data-testid="stHorizontalBlock"]:has(.brand) > [data-testid="stColumn"]:nth-child({k}) a p, '
        f'[data-testid="stHorizontalBlock"]:has(.brand) > [data-testid="stColumn"]:nth-child({k}) a span '
        '{ color: #fff !important; }</style>')
current.run()
