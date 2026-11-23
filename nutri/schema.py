"""What the models must return (strict JSON schemas), validated with pydantic."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LABELS = ("allowed", "crisis", "emergency", "harmful", "manipulation")


class Screen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: Literal["allowed", "crisis", "emergency", "harmful", "manipulation"]
    reason: str


class Sentence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    sources: list[int]


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    covered: bool = Field(description="True only if the numbered sources answer the question")
    sentences: list[Sentence] = Field(description="The reply, one sentence at a time, each with its source numbers")
    see_a_professional: bool

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.sentences)


class Standalone(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str


class Judgement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unsupported: list[str] = Field(description="Claims in the reply that the sources do not state")
    answers_question: bool


def strict(model: type[BaseModel]) -> dict:
    """The pydantic schema in the form Groq's strict mode accepts (every property required, no extras)."""
    s = model.model_json_schema()

    def tidy(obj: dict) -> None:
        obj.pop("title", None)
        obj.pop("description", None)
        if "properties" in obj:
            obj["additionalProperties"] = False
            obj["required"] = list(obj["properties"])
            for p in obj["properties"].values():
                tidy(p)
        if "items" in obj:
            tidy(obj["items"])

    tidy(s)
    for d in s.get("$defs", {}).values():
        tidy(d)
    return s
