"""One turn: screen the message, make it standalone, search, answer from the sources, check the citations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import prompts
from .corpus import Passage
from .llm import Client
from .schema import Answer, Judgement, Screen, Standalone, strict

SCREEN_MODEL = "openai/gpt-oss-safeguard-20b"
REWRITE_MODEL = "openai/gpt-oss-20b"
ANSWER_MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
K = 5

FIXED = {
    "crisis": ("It sounds like you are going through something really hard, and you deserve support right now. "
               "Please reach out to someone today: if you are in immediate danger, call your local emergency number. "
               "In the U.S. you can call or text 988 (Suicide and Crisis Lifeline); elsewhere, findahelpline.com "
               "lists free, confidential lines in your country. Talking to a doctor, or someone you trust, is a "
               "strong first step."),
    "emergency": ("This sounds like it needs urgent care now. Call your local emergency number. For a swallowed "
                  "overdose or poisoning in the U.S., call Poison Help at 1-800-222-1222 (open 24 hours); elsewhere, "
                  "your emergency number or local poison centre. Do not wait for symptoms, and do not try to treat "
                  "it at home first."),
    "harmful": ("I can't help with that, because it could seriously harm your health. If food, weight or a "
                "treatment is worrying you, a doctor or registered dietitian can help you find a safe plan. If you "
                "are struggling with eating, the Eating Disorders page from MedlinePlus explains that these are "
                "real, treatable illnesses."),
    "manipulation": ("I can only answer nutrition questions from my NIH sources. Ask me about vitamins, minerals, "
                     "anemia, weight, digestive conditions and healthy eating."),
}


@dataclass
class Turn:
    question: str
    label: str = "allowed"
    standalone: str = ""
    passages: list[Passage] = field(default_factory=list)
    answer: Answer | None = None
    text: str = ""
    cited: list[int] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    tokens: int = 0
    seconds: float = 0.0
    error: str = ""


def history_text(history: list[tuple[str, str]], last: int = 3) -> str:
    return "\n".join(f"User: {q}\nAssistant: {a}" for q, a in history[-last:])


REFER = re.compile(r"\b(doctor|dietitian|health ?care provider|professional|clinician|pharmacist)\b", re.I)


def check(answer: Answer, n_sources: int) -> tuple[list[int], list[str]]:
    """Every sentence of a covered answer cites a source that was given (sentences that only refer the person to a
    doctor or dietitian may cite none), and the length stays readable."""
    cited = sorted({c for s in answer.sentences for c in s.sources})
    problems = []
    if any(c < 1 or c > n_sources for c in cited):
        problems.append("cites a source that was not given")
    if answer.covered:
        bare = [s for s in answer.sentences if not s.sources and not REFER.search(s.text)]
        if bare:
            problems.append(f"{len(bare)} sentence(s) without a source")
        words = len(answer.text.split())
        if not 30 <= words <= 260:
            problems.append(f"length {words} words")
    return cited, problems


def screen(client: Client, question: str, history: list[tuple[str, str]]) -> tuple[Screen | None, int]:
    user = (f"Earlier turns:\n{history_text(history)}\n\n" if history else "") + f"Latest message:\n{question}"
    s, call, _ = client.structured(SCREEN_MODEL, prompts.SCREEN, user, strict(Screen), Screen.model_validate_json,
                                   tag="screen", max_tokens=400)
    return s, call.prompt_tokens + call.completion_tokens


def run(client: Client, retriever, question: str, model: str, history: list[tuple[str, str]] | None = None,
        profile: dict | None = None, use_screen: bool = True) -> Turn:
    history = history or []
    t = Turn(question)
    if use_screen:
        s, tok = screen(client, question, history)
        t.tokens += tok
        t.label = s.label if s else "allowed"
        if t.label in FIXED:
            t.text = FIXED[t.label]
            return t
    t.standalone = question
    if history:
        r, call, _ = client.structured(REWRITE_MODEL, prompts.STANDALONE,
                                       f"Conversation:\n{history_text(history)}\n\nLatest message: {question}",
                                       strict(Standalone), Standalone.model_validate_json, tag="rewrite",
                                       max_tokens=300)
        t.tokens += call.prompt_tokens + call.completion_tokens
        t.standalone = r.question if r else question
    t.passages = [p for p, _ in retriever.search(t.standalone, k=K)]
    user = (prompts.profile_line(profile) + f"Question: {question}"
            + (f"\n(Standalone form: {t.standalone})" if t.standalone != question else "")
            + f"\n\nSources:\n{prompts.sources_block(t.passages)}")
    a, call, err = client.structured(model, prompts.ANSWER, user, strict(Answer), Answer.model_validate_json,
                                     tag="answer", max_tokens=1200)
    t.tokens += call.prompt_tokens + call.completion_tokens
    t.seconds = call.seconds
    if a is None:
        t.error = err or "no valid answer"
        t.text = "Sorry, I could not put an answer together this time. Please try again."
        return t
    t.answer = a
    t.text = a.text
    t.cited, t.problems = check(a, len(t.passages))
    return t


def judge(client: Client, model: str, turn: Turn) -> Judgement | None:
    user = (f"Question: {turn.question}\n\nSources:\n{prompts.sources_block(turn.passages)}\n\n"
            f"Reply:\n{turn.text}")
    j, _, _ = client.structured(model, prompts.JUDGE, user, strict(Judgement), Judgement.model_validate_json,
                                tag="judge", max_tokens=700)
    return j
