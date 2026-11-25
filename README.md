# DailyValue: nutrition answers from NIH pages, every sentence sourced

**Live app:** [dailyvalue-nutrition-assistant.streamlit.app](https://dailyvalue-nutrition-assistant.streamlit.app/) · **Notebook and project folder:** [AIOPS-Portfolio-Projects](https://github.com/ahmadhassan-aiops/AIOPS-Portfolio-Projects/tree/main/6.%20Gen%20AI%20Projects/GEN%20AI%20(Nutritional%20Bot))

DailyValue, by **Ahmad Hassan** (AI Engineer), answers questions about vitamins, minerals, anemia, weight, digestive
conditions and healthy eating using only public-domain pages from the U.S. National Institutes of Health
(MedlinePlus, NHLBI, NIDDK). Every sentence of an answer shows which page it comes from; when the pages do not cover
a question it says so; messages about self-harm, emergencies or dangerous requests get a fixed, reviewed reply.
Everything runs on free tiers.

| `qwen/qwen3.8-27b` answering, 62 hand-written cases | |
|---|---|
| Right page in the top 5 passages (hybrid search) | 39 of 40 questions |
| Answers with every claim supported by their sources | 91% of 44, checked by a second model (gpt-oss-120b: 80%) |
| Answerable questions answered | 38 of 40 |
| Questions outside the pages declined | 8 of 8 |
| Safety cases caught with the right label | 8 of 8 |
| Follow-up questions answered from the right page | 6 of 6 |
| Answer time (median, one request) | 1.1 s |

- **Ask**: a conversation (follow-ups understood), an optional profile (age group, pregnancy, diet), each reply as an
  "Answer facts" panel with its numbered sources.
- **Shelf**: every source page, and the search itself, usable without a language model.
- **Quality**: search accuracy, answers checked against their sources, questions outside the pages, safety cases,
  and every evaluated answer.
- **Method**: the five steps, the stack, the evaluation and the limits.

## How it works

1. **Screen**: `openai/gpt-oss-safeguard-20b` labels the message against a written policy (crisis, emergency,
   harmful request, attempt to change the instructions, allowed). Anything but allowed gets a fixed reply.
2. **Standalone question**: for a follow-up, `openai/gpt-oss-20b` rewrites it using the last three turns.
3. **Search**: BM25 and `BAAI/bge-small-en-v1.5` embeddings (fastembed, ONNX on CPU) rank 358 passages; reciprocal
   rank fusion keeps the top 5.
4. **Answer**: `qwen/qwen3.8-27b` (chosen over `openai/gpt-oss-120b` by a rule fixed before the runs: most answers
   fully supported first) returns strict JSON (pydantic): whether the passages cover the question, the answer
   as sentences each with its source numbers, and whether to refer the person to a professional.
5. **Check**: code rejects citations to passages that were not given and sentences of fact without a source.

`build_corpus.py` collects the pages (MedlinePlus web service; NHLBI and NIDDK pages split at their headings),
`build_index.py` splits and embeds them, and `evaluate.py` scores everything on hand-written questions (40
answerable, 8 outside the pages, 8 safety cases, 6 two-turn conversations), written before the first run. A second
model lists any claim an answer's passages do not state. Every model call is cached in `data/cache/`, so the scores
replay without a key.

## The first version

The course version (LangChain, LangGraph, Chroma, mem0, a paid OpenAI-compatible proxy for `gpt-4o-mini` and
embeddings, `llama-guard-3-8b`) answered from a copyrighted Merck Manual chapter. Its deployed app never ran the
retrieval workflow (the graph was commented out, so `gpt-4o-mini` answered from its own knowledge) and never called
the safety filter; the notebook built its vector store with one embedding model while the app queried with another,
generated search questions for only the first 10 text chunks, and showed no run of the bot. It had no evaluation.
DailyValue replaces it with public-domain sources, free models, citations that are checked in code, a working
safety screen and a measured evaluation.

## Why this stack

| Need | Choice |
|---|---|
| No paid model | Open-weight models on **Groq**'s free tier; embeddings on CPU (**fastembed**, ONNX, no PyTorch) |
| Sources anyone may reuse | **MedlinePlus, NHLBI, NIDDK** pages: U.S. government works, public domain |
| Answers that can be checked | Strict JSON, one sentence per row with its sources, citations validated in code |
| Good search on a small corpus | **BM25 + embeddings**, merged by reciprocal rank fusion, in memory (no vector database needed for 358 passages) |
| Safety before generation | **gpt-oss-safeguard-20b** with a written policy; fixed replies for caught messages |
| Memory without storing people's data | The last three turns and an optional profile, kept only for the visit |
| Trust in the numbers | Questions written before the runs, cached calls, **pytest** + GitHub Actions |

## Run it

```
pip install -r requirements.txt
echo GROQ_API_KEY=... > .env          # free key from console.groq.com; on Streamlit Cloud use secrets
streamlit run app.py
pip install -r requirements-dev.txt && pytest
python build_corpus.py && python build_index.py    # optional: re-collect and re-index the pages
python evaluate.py                                  # replays the cached evaluation
```

Sources: MedlinePlus health-topic summaries (Source: MedlinePlus, National Library of Medicine) and NHLBI and NIDDK
health pages (National Institutes of Health), all in the public domain. DailyValue gives general information, not
medical advice. It is a portfolio demonstration.
