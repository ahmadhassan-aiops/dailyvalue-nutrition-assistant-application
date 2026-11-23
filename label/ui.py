"""DailyValue components: a nutrition facts label. Every block is a white label with a black border and a heavy rule
under its title; an answer is an "Answer facts" panel whose rows are sentences and whose right-hand column holds the
source numbers where a label shows % Daily Value."""

from __future__ import annotations

import html
from contextlib import contextmanager

import streamlit as st

from label import theme as t
from label._controls import CONTROLS
from label.site import CODE_URL, DATA_CREDIT, DISCLAIMER, LEARN_URL, NOTEBOOK_URL

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:ital,wdth,wght@0,62..125,400..900;1,100,400&family=Spline+Sans+Mono:wght@400;500;600&display=swap');
:root {{ --counter:{t.COUNTER}; --label:{t.LABEL}; --ink:{t.INK}; --muted:{t.MUTED}; --faint:{t.FAINT}; --rule:{t.RULE};
         --soft-rule:{t.SOFT_RULE}; --accent:{t.ACCENT}; --hl:{t.HIGHLIGHT}; --hl-soft:{t.HIGHLIGHT_SOFT};
         --head:{t.HEAD}; --body:{t.BODY}; --mono:{t.MONO}; }}
html, body, [data-testid="stAppViewContainer"] {{ font-family: var(--body); color: var(--ink); }}
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stBottom"] > div {{ background: var(--counter); }}
.block-container {{ padding-top: 4.1rem; max-width: 1220px; }}
header[data-testid="stHeader"] {{ background: var(--counter); }}
.msr {{ font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; line-height: 1; display: inline-block;
        -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga'; -webkit-font-smoothing: antialiased; }}

/* Labels: white, black border, square corners */
[data-testid="stVerticalBlock"][data-test-scroll-behavior] {{ border: 1.5px solid var(--rule) !important; border-radius: 0 !important;
    background: var(--label); box-shadow: 4px 4px 0 rgba(20, 20, 20, .12); padding: .9rem 1.1rem 1rem !important; }}
[data-testid="stVerticalBlock"][data-test-scroll-behavior][class*="st-key-main_"] {{ box-shadow: 6px 6px 0 var(--hl) !important; }}

/* Navigation: the label's name, then the sections as tabs over a heavy rule */
[data-testid="stHorizontalBlock"]:has(.brand) {{ gap: .3rem; align-items: end; margin-bottom: .2rem; padding-bottom: .55rem;
    border-bottom: 10px solid var(--rule); }}
.brand {{ display: flex; align-items: center; gap: .65rem; }}
.brand .name {{ font-family: var(--head); font-weight: 900; font-stretch: 72%; font-size: 2.35rem; margin: 0; line-height: .9; letter-spacing: -.01em; }}
.brand .tagline {{ font-size: .8rem; color: var(--muted); margin: .3rem 0 0; font-weight: 500; white-space: nowrap; }}
.brand .mk {{ width: 3rem; height: 3rem; flex: none; background: var(--ink); color: var(--hl); display: grid; place-items: center; }}
.brand .mk .msr {{ font-size: 1.5rem; }}
[data-testid="stHorizontalBlock"]:has(.brand) [data-testid="stPageLink"] a {{ justify-content: center; border-radius: 0; padding: .4rem .5rem;
    background: var(--label); border: 1.5px solid var(--rule); }}
[data-testid="stHorizontalBlock"]:has(.brand) [data-testid="stPageLink"] a p {{ font-family: var(--head); font-weight: 800; font-stretch: 85%;
    font-size: 1rem; color: var(--ink); white-space: nowrap; letter-spacing: .01em; }}
[data-testid="stHorizontalBlock"]:has(.brand) [data-testid="stPageLink"] a span {{ color: var(--ink); }}
[data-testid="stHorizontalBlock"]:has(.brand) [data-testid="stPageLink"] a:hover {{ background: var(--hl-soft); }}
[data-testid="stHorizontalBlock"]:has(.brand) [data-testid="stPageLink"] a:focus-visible {{ outline: 2px solid var(--accent) !important; outline-offset: 2px; }}

/* Chat box: a label strip pinned to the bottom */
[data-testid="stChatInput"] > div {{ border: 1.5px solid var(--rule) !important; border-radius: 0 !important; background: var(--label) !important;
    box-shadow: 4px 4px 0 var(--hl) !important; }}
[data-testid="stChatInput"]:focus-within > div {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
[data-testid="stChatInput"] textarea {{ font-family: var(--body); font-size: 1rem; color: var(--ink); }}
[data-testid="stChatInputSubmitButton"] {{ border-radius: 0 !important; background: var(--ink) !important; color: #fff !important; }}
.visit p {{ margin: 0; padding: .4rem 0; border-bottom: 1px solid var(--rule); font-size: .9rem; line-height: 1.45; }}
.visit p b {{ display: block; font-size: .78rem; font-weight: 800; }}
.visit p .big {{ font-family: var(--head); font-weight: 900; font-stretch: 80%; font-size: 1.6rem; line-height: 1.1; }}

/* Page head */
.kicker {{ font-family: var(--mono); font-size: .76rem; color: var(--muted); margin: 1.2rem 0 .3rem; letter-spacing: .04em; }}
.kicker b {{ color: var(--accent); }}
.title {{ font-family: var(--head); font-size: 2.6rem; font-weight: 900; font-stretch: 78%; margin: 0; line-height: 1.02; }}
.lead {{ color: var(--muted); font-size: 1.04rem; line-height: 1.6; max-width: 830px; margin: .55rem 0 1.1rem; }}
.lead b {{ color: var(--ink); }}

/* Panel title: bold condensed heading over a heavy rule */
.lh {{ display: flex; align-items: baseline; gap: .6rem; margin: 0; padding-bottom: .15rem; border-bottom: 7px solid var(--rule); }}
.lh .no {{ font-family: var(--mono); font-size: .74rem; color: var(--faint); }}
.lh .t {{ font-family: var(--head); font-weight: 900; font-stretch: 80%; font-size: 1.45rem; margin: 0; line-height: 1.05; }}
.lh .ic {{ margin-left: auto; color: var(--ink); align-self: center; }}
.lh .ic .msr {{ font-size: 1.4rem; }}
.sub {{ font-size: .9rem; color: var(--muted); margin: .45rem 0 .7rem; line-height: 1.5; padding-bottom: .45rem; border-bottom: 1px solid var(--rule); }}

/* Tiles: amount-per-serving boxes */
.tiles {{ display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: .6rem; margin: 0 0 1rem; }}
@media (max-width: 860px) {{ .tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
.tile {{ background: var(--label); border: 1.5px solid var(--rule); padding: .5rem .8rem .6rem; }}
.tile.hl {{ box-shadow: 4px 4px 0 var(--hl); }}
.tile-l {{ font-size: .78rem; font-weight: 800; margin: 0; padding-bottom: .25rem; border-bottom: 4px solid var(--rule); }}
.tile-v {{ font-family: var(--head); font-size: 2.1rem; font-weight: 900; font-stretch: 80%; margin: .15rem 0 0; line-height: 1.1; }}
.tile-n {{ font-size: .79rem; color: var(--muted); margin: 0; line-height: 1.4; }}

/* Answer facts */
.af {{ border: 1.5px solid var(--rule); background: var(--label); padding: .55rem .9rem .7rem; }}
.af .q {{ font-size: .92rem; color: var(--muted); margin: 0 0 .25rem; }}
.af .q b {{ color: var(--ink); }}
.af .h {{ font-family: var(--head); font-weight: 900; font-stretch: 75%; font-size: 2.15rem; line-height: 1; margin: 0; }}
.af .meta {{ display: flex; justify-content: space-between; font-size: .88rem; padding: .25rem 0; border-bottom: 10px solid var(--rule); }}
.af .meta b {{ font-weight: 800; }}
.af .col {{ display: flex; justify-content: flex-end; font-size: .74rem; font-weight: 800; padding: .2rem 0; border-bottom: 1px solid var(--rule); }}
.af .s {{ display: grid; grid-template-columns: 1fr auto; gap: .9rem; padding: .42rem 0; border-bottom: 1px solid var(--rule); align-items: start; }}
.af .s p {{ margin: 0; font-size: 1rem; line-height: 1.55; }}
.af .s:hover p {{ background: var(--hl-soft); }}
.af .refs {{ display: flex; gap: .2rem; justify-content: flex-end; flex-wrap: wrap; }}
.af .ref {{ font-family: var(--mono); font-size: .78rem; font-weight: 600; min-width: 1.55rem; text-align: center; padding: .05rem .3rem;
            border: 1.5px solid var(--rule); background: var(--hl); }}
.af .ref.none {{ background: transparent; border-style: dashed; color: var(--faint); }}
.af .thick {{ border-bottom: 5px solid var(--rule); margin-top: -1px; }}
.af .foot {{ font-size: .8rem; color: var(--muted); line-height: 1.5; margin: .45rem 0 0; }}
.af .pro {{ display: flex; gap: .45rem; align-items: center; margin: .55rem 0 0; font-weight: 700; font-size: .9rem; }}
.af .pro .msr {{ font-size: 1.15rem; }}
.af.nocover .h {{ color: var(--muted); }}
.src {{ display: grid; grid-template-columns: 1.8rem 1fr; gap: .1rem .55rem; padding: .45rem 0; border-bottom: 1px solid var(--soft-rule); }}
.src:last-child {{ border-bottom: 0; }}
.src .n {{ font-family: var(--mono); font-weight: 600; font-size: .8rem; text-align: center; border: 1.5px solid var(--rule); height: 1.45rem;
           line-height: 1.3rem; }}
.src .n.used {{ background: var(--hl); }}
.src .ti {{ font-weight: 700; font-size: .9rem; line-height: 1.35; }}
.src .ti a {{ color: var(--ink); text-decoration-color: var(--accent); text-underline-offset: 2px; }}
.src .ti a:hover {{ color: var(--accent); }}
.src .x {{ grid-column: 2; font-size: .84rem; color: var(--muted); line-height: 1.5; }}
.org {{ display: inline-block; font-size: .68rem; font-weight: 800; letter-spacing: .05em; color: #fff; background: var(--c); padding: .02rem .4rem;
        margin-right: .35rem; vertical-align: 1px; }}
.you {{ display: flex; justify-content: flex-end; margin: 1rem 0 .45rem; }}
.you p {{ margin: 0; max-width: 80%; background: var(--ink); color: #fff; padding: .55rem .85rem; font-size: .98rem; line-height: 1.5; }}
.you p .rw {{ display: block; font-family: var(--mono); font-size: .72rem; color: #cfcfcf; margin-top: .25rem; }}

/* Safety card */
.warn {{ border: 3px solid var(--c); background: var(--label); padding: .7rem .95rem .8rem; }}
.warn .h {{ display: flex; gap: .5rem; align-items: center; font-family: var(--head); font-weight: 900; font-stretch: 80%; font-size: 1.45rem;
            color: var(--c); margin: 0 0 .45rem; padding-bottom: .3rem; border-bottom: 5px solid var(--c); }}
.warn .h .msr {{ font-size: 1.6rem; }}
.warn p {{ margin: 0; font-size: 1rem; line-height: 1.6; }}

/* Tables */
.tbl {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
.tbl th {{ font-size: .76rem; font-weight: 800; text-align: left; padding: .35rem .5rem; border-bottom: 5px solid var(--rule); }}
.tbl td {{ padding: .42rem .5rem; border-bottom: 1px solid var(--rule); vertical-align: top; line-height: 1.45; }}
.tbl th.n, .tbl td.n {{ text-align: right; }}
.tbl td.n {{ font-family: var(--mono); white-space: nowrap; }}
.tbl tr.pick td {{ background: var(--hl-soft); font-weight: 700; }}
.tbl tr.base td {{ color: var(--muted); }}
.ok {{ font-weight: 800; color: #2f6b3a; }}
.no {{ font-weight: 800; color: #a3332b; }}

/* Notes */
.notes {{ margin: .9rem 0 0; border: 1.5px dashed var(--rule); padding: .5rem .85rem .35rem; }}
.notes .h {{ font-size: .74rem; font-weight: 800; letter-spacing: .06em; margin: 0 0 .3rem; display: flex; gap: .35rem; align-items: center; }}
.notes .h .msr {{ font-size: 1rem; }}
.notes ul {{ margin: 0; padding-left: 1.1rem; }}
.notes li {{ font-size: .91rem; line-height: 1.55; margin: 0 0 .35rem; }}
.takeaway {{ display: flex; gap: .7rem; align-items: flex-start; margin: .9rem 0 0; padding: .65rem .9rem; background: var(--hl-soft);
             border-left: 6px solid var(--rule); font-size: .97rem; line-height: 1.55; }}
.takeaway .msr {{ font-size: 1.35rem; }}
.caution {{ display: flex; gap: .55rem; border: 1px solid var(--rule); padding: .5rem .8rem; margin: .7rem 0 0; font-size: .87rem;
            line-height: 1.5; background: var(--label); }}
.caution .msr {{ color: var(--accent); font-size: 1.2rem; }}
.facts {{ display: grid; grid-template-columns: minmax(9rem, 27%) 1fr; margin: 0; padding: 0 !important; }}
.facts dt, .facts dd {{ padding: .48rem .3rem; border-bottom: 1px solid var(--rule); margin: 0; font-size: .92rem; line-height: 1.5; }}
.facts dt {{ font-weight: 800; font-size: .86rem; }}
.steps {{ counter-reset: s; margin: 0; padding: 0; list-style: none; }}
.steps li {{ counter-increment: s; display: grid; grid-template-columns: 2.1rem 1fr; gap: .6rem; padding: .5rem 0; border-bottom: 1px solid var(--rule);
             font-size: .93rem; line-height: 1.5; }}
.steps li::before {{ content: counter(s); font-family: var(--head); font-weight: 900; font-size: 1.35rem; background: var(--ink); color: var(--hl);
                     text-align: center; height: 2.1rem; line-height: 2.1rem; }}
.steps b {{ display: block; }}
.foot {{ margin: 2rem 0 .5rem; border-top: 10px solid var(--rule); display: flex; flex-wrap: wrap; font-size: .86rem; color: var(--muted); }}
.foot > * {{ padding: .6rem 1rem .5rem 0; margin-right: 1rem; }}
.foot b {{ color: var(--ink); }}
.foot a {{ color: var(--ink); font-weight: 800; text-decoration-color: var(--accent); text-underline-offset: 3px; }}
.foot a:hover {{ color: var(--accent); }}
.foot .credit {{ flex-basis: 100%; padding-top: 0; font-size: .79rem; color: var(--faint); }}
</style>
"""


def inject_css() -> None:
    st.html(CSS + CONTROLS)


def icon(name: str) -> str:
    return f'<span class="msr" aria-hidden="true">{name}</span>'


def esc(text) -> str:
    return html.escape(str(text))


def page(code: str, name: str, title: str, lead: str) -> None:
    st.html(f'<p class="kicker"><b>{esc(code)}</b> · {esc(name)}</p><h1 class="title">{esc(title)}</h1><p class="lead">{lead}</p>')


@contextmanager
def panel(no: str, title: str, pictogram: str, sub: str = "", main: bool = False):
    with st.container(border=True, key=f"main_{no}" if main else None):
        st.html(f'<div class="lh"><span class="no">{esc(no)}</span><p class="t">{esc(title)}</p>'
                f'<span class="ic">{icon(pictogram)}</span></div>' + (f'<p class="sub">{sub}</p>' if sub else
                                                                     '<div style="height:.6rem"></div>'))
        yield


def tiles(items: list[tuple[str, str, str]], highlight: int | None = None) -> None:
    body = "".join(f'<div class="tile{" hl" if i == highlight else ""}"><p class="tile-l">{esc(l)}</p>'
                   f'<p class="tile-v">{v}</p><p class="tile-n">{n}</p></div>' for i, (l, v, n) in enumerate(items))
    st.html(f'<div class="tiles" style="--n:{len(items)}">{body}</div>')


def org(source: str) -> str:
    key = next((k for k in t.ORG_COLOR if source.startswith(k)), "MedlinePlus")
    return f'<span class="org" style="--c:{t.ORG_COLOR[key]}">{key}</span>'


def answer_facts(question: str, sentences: list[dict], covered: bool, professional: bool, n_sources: int,
                 standalone: str = "") -> str:
    """The answer as a facts panel: one row per sentence, its source numbers on the right."""
    cited = sorted({c for s in sentences for c in s["sources"]})
    rows = ""
    for s in sentences:
        refs = "".join(f'<span class="ref">{c}</span>' for c in s["sources"]) or '<span class="ref none">-</span>'
        rows += f'<div class="s"><p>{esc(s["text"])}</p><div class="refs">{refs}</div></div>'
    head = "Answer facts" if covered else "Not in these sources"
    meta = (f'<div class="meta"><span>{len(sentences)} sentence{"s" if len(sentences) != 1 else ""}</span>'
            f'<span><b>Sources cited</b> {len(cited)} of {n_sources}</span></div>')
    pro = (f'<p class="pro">{icon("stethoscope")}Ask a doctor or registered dietitian about your own case.</p>'
           if professional else "")
    rw = (f'<p class="q">Searched as: <b>{esc(standalone)}</b></p>' if standalone and standalone != question else "")
    return (f'<div class="af{"" if covered else " nocover"}"><p class="h">{head}</p>{meta}'
            f'<div class="col">Source</div>{rows}<div class="thick"></div>{pro}{rw}'
            f'<p class="foot">Every row comes from the numbered NIH pages below. General information, not medical '
            f'advice.</p></div>')


def sources_list(passages: list[dict], cited: list[int]) -> str:
    out = ""
    for i, p in enumerate(passages, 1):
        snippet = p["text"][:260].rsplit(" ", 1)[0] + ("..." if len(p["text"]) > 260 else "")
        out += (f'<div class="src"><span class="n{" used" if i in cited else ""}">{i}</span>'
                f'<span class="ti">{org(p["source"])}<a href="{esc(p["url"])}" target="_blank">{esc(p["title"])}</a></span>'
                f'<span class="x">{esc(snippet)}</span></div>')
    return out


def safety_card(label: str, text: str) -> str:
    head, pic, color = t.SAFETY[label]
    return f'<div class="warn" style="--c:{color}"><p class="h">{icon(pic)}{esc(head)}</p><p>{esc(text)}</p></div>'


def you(text: str, standalone: str = "") -> None:
    rw = f'<span class="rw">searched as: {esc(standalone)}</span>' if standalone and standalone != text else ""
    st.html(f'<div class="you"><p>{esc(text)}{rw}</p></div>')


def notes(*items: str) -> None:
    st.html(f'<div class="notes"><p class="h">{icon("edit_note")}NOTES</p><ul>' + "".join(f"<li>{i}</li>" for i in items)
            + "</ul></div>")


def takeaway(text: str) -> None:
    st.html(f'<div class="takeaway">{icon("lightbulb")}<div>{text}</div></div>')


def caution(text: str, pictogram: str = "info") -> None:
    st.html(f'<div class="caution">{icon(pictogram)}<div>{text}</div></div>')


def pct(x) -> str:
    return "-" if x is None else f"{x:.0%}"


def footer() -> None:
    st.html(f'<div class="foot"><span>DailyValue · <b>Ahmad Hassan</b>, AI Engineer</span>'
            f'<a href="{NOTEBOOK_URL}" target="_blank">Notebook</a><a href="{CODE_URL}" target="_blank">App code</a>'
            f'<a href="{LEARN_URL}" target="_blank">Learn with Ahmad</a><span class="credit">{esc(DISCLAIMER)} '
            f'{esc(DATA_CREDIT)}</span></div>')
