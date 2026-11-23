"""Collects the knowledge base from U.S. government health pages, which are in the public domain:

- MedlinePlus health-topic summaries (National Library of Medicine), through the MedlinePlus web service;
- NHLBI and NIDDK (National Institutes of Health) pages on anemia, obesity, the metabolic syndrome and diet-related
  digestive conditions, which go into more detail than the summaries.

    python build_corpus.py        # writes data/sources.jsonl (one topic per line)

Only health-topic pages are kept (https://medlineplus.gov/<topic>.html); A.D.A.M. encyclopedia articles, which are
copyrighted, are never fetched. NIH pages are split at their section headings.
"""

from __future__ import annotations

import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

API = "https://wsearch.nlm.nih.gov/ws/query"
OUT = Path(__file__).parent / "data" / "sources.jsonl"
TOPIC_URL = re.compile(r"^https://medlineplus\.gov/[a-z0-9]+\.html$")
OFF_TOPIC = {"https://medlineplus.gov/hyperthyroidism.html", "https://medlineplus.gov/toothdecay.html"}  # best hits for iodine, fluoride

# The scope of the course reference (nutrition basics, undernutrition, nutritional support, vitamins, minerals,
# obesity and the metabolic syndrome), as search terms.
TERMS = [
    "nutrition", "carbohydrates", "dietary fats", "dietary proteins", "dietary fiber", "calories", "cholesterol",
    "dietary supplements", "water in diet dehydration", "malnutrition", "nutrition for older adults",
    "infant and newborn nutrition", "child nutrition", "nutrition in pregnancy", "nutritional support",
    "enteral nutrition feeding tube", "eating disorders", "vitamins", "vitamin a", "b vitamins", "vitamin b12",
    "folic acid", "vitamin c", "vitamin d", "vitamin d deficiency", "vitamin e", "vitamin k", "minerals",
    "calcium", "iron", "iron deficiency anemia", "anemia", "pernicious anemia", "iodine", "magnesium",
    "potassium", "sodium", "zinc", "fluoride", "obesity", "obesity in children", "metabolic syndrome",
    "weight control", "weight loss surgery", "celiac disease", "osteoporosis", "scurvy rickets", "food allergy",
    "lactose intolerance", "diabetic diet",
]


NIH_PAGES = [
    ("NHLBI", "https://www.nhlbi.nih.gov/health/anemia"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/anemia/causes"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/anemia/symptoms"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/anemia/diagnosis"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/anemia/treatment"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/anemia/iron-deficiency-anemia"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/anemia/vitamin-b12-deficiency-anemia"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/anemia/pregnancy"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/metabolic-syndrome"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/metabolic-syndrome/causes"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/metabolic-syndrome/symptoms"),
    ("NHLBI", "https://www.nhlbi.nih.gov/health/metabolic-syndrome/treatment"),
    ("NIDDK", "https://www.niddk.nih.gov/health-information/weight-management/adult-overweight-obesity/all-content"),
    ("NIDDK", "https://www.niddk.nih.gov/health-information/weight-management/bariatric-surgery/all-content"),
    ("NIDDK", "https://www.niddk.nih.gov/health-information/digestive-diseases/celiac-disease/all-content"),
    ("NIDDK", "https://www.niddk.nih.gov/health-information/digestive-diseases/lactose-intolerance/all-content"),
    ("NIDDK", "https://www.niddk.nih.gov/health-information/liver-disease/hemochromatosis/all-content"),
    ("NIDDK", "https://www.niddk.nih.gov/health-information/digestive-diseases/short-bowel-syndrome/all-content"),
]
SKIP = re.compile(r"^(Language switcher|IN THIS ARTICLE|Clinical Trials|References|Related|More information|"
                  r"Participate|Last updated|This content is provided|Book traversal|Previous|Next)", re.I)
TRIALS = re.compile(r"clinical (trial|stud)|NIDDK-funded research|how much does .* cost", re.I)


def nih_page(org: str, url: str) -> list[dict]:
    """The page's main article, one record per section (h2/h3), without menus, trial ads or references."""
    r = requests.get(url, timeout=30, headers={"User-Agent": "dailyvalue-corpus-builder"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.find("main") or soup.body
    for t in main(["script", "style", "nav", "aside", "footer", "form", "button"]):
        t.decompose()
    for t in main.select('[class*="usa-modal"]'):         # NHLBI glossary pop-ups (pronunciation + definition)
        t.decompose()
    h1 = main.find("h1")
    page = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else url
    m = re.match(r"^(Anemia|Metabolic Syndrome) (.+)$", page) if org == "NHLBI" else None
    if m:                                    # "Anemia Symptoms" -> "Anemia: Symptoms"; "Anemia Iron-Deficiency Anemia" -> the type
        page = m[2] if m[1].lower() in m[2].lower() else f"{m[1]}: {m[2]}"
    sections, head, buf = [], page, []
    start = h1 or main
    for el in start.find_all_next(["h2", "h3", "p", "li", "td", "th"]):
        if el.name in ("h2", "h3"):
            h = el.get_text(" ", strip=True)
            if SKIP.match(h) and not buf:        # a language switcher before the text: keep the page title
                continue
            if head and buf:
                sections.append((head, buf))
            head, buf = h, []
            continue
        if el.find_parent(["li", "td"]) is not None and el.name == "p":
            continue
        t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if el.name == "li" and t in ("Accessibility", "Privacy", "Disclaimer", "FOIA", "Contact Us"):
            break                            # the site footer: the article is over
        if t and t not in ("English", "Español"):
            buf.append(("- " if el.name == "li" else "") + t)
    if head and buf:
        sections.append((head, buf))
    out = []
    for head, lines in sections:
        if SKIP.match(head) or TRIALS.search(head) or len(" ".join(lines).split()) < 25:
            continue
        out.append({"url": url, "title": page if head == page else f"{page}: {head}", "also_called": [], "text": "\n".join(lines),
                    "source": f"{org}, National Institutes of Health"})
    return out


def text(summary: str) -> str:
    s = html.unescape(re.sub(r'<span class="qt\d+">|</span>', "", summary))
    s = re.sub(r"</?(p|ul|ol)>", "\n", s)
    s = re.sub(r"<li>", "\n- ", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n\n", re.sub(r"[ \t]+", " ", s)).strip()


def search(term: str) -> list[dict]:
    r = requests.get(API, params={"db": "healthTopics", "term": term, "retmax": 5}, timeout=30,
                     headers={"User-Agent": "dailyvalue-corpus-builder"})
    r.raise_for_status()
    out = []
    for doc in ET.fromstring(r.content).iter("document"):
        f = {}
        for c in doc.iter("content"):
            f.setdefault(c.get("name"), []).append("".join(c.itertext()))
        out.append({"url": doc.get("url"), "title": text(f.get("title", [""])[0]),
                    "also_called": [text(a) for a in f.get("altTitle", [])],
                    "text": text(f.get("FullSummary", [""])[0])})
    return out


def main() -> None:
    topics: dict[str, dict] = {}
    for term in TERMS:
        hits = [h for h in search(term) if TOPIC_URL.match(h["url"] or "") and h["text"] and h["url"] not in OFF_TOPIC]
        if hits and hits[0]["url"] not in topics:     # the best health-topic match for each term
            topics[hits[0]["url"]] = {**hits[0], "term": term}
        time.sleep(0.4)                                # the service asks for at most 85 requests a minute
    records = [{**t, "source": "MedlinePlus, National Library of Medicine"} for t in topics.values()]
    for org, url in NIH_PAGES:
        try:
            got = nih_page(org, url)
        except requests.HTTPError as e:
            print("skipped", url, e)
            continue
        print(f"{len(got):3} sections  {url}")
        records += got
        time.sleep(1)
    today = date.today().isoformat()
    with OUT.open("w", encoding="utf-8") as f:
        for t in records:
            f.write(json.dumps({**t, "retrieved": today}, ensure_ascii=False) + "\n")
    words = sum(len(t["text"].split()) for t in records)
    print(f"{len(topics)} MedlinePlus topics + {len(records) - len(topics)} NIH sections, {words:,} words -> {OUT}")


if __name__ == "__main__":
    main()
