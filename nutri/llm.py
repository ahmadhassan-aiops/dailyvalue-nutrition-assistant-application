"""Calls to open models served by Groq (shared plumbing with DeskBrief and CaseRoute), with an optional on-disk cache so evaluations can be replayed for free."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError


try:   # use the operating system's certificates where Python's own bundle is not enough (optional)
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass


def api_key() -> str | None:
    """GROQ_API_KEY from Streamlit secrets (on Streamlit Cloud) or the environment / a local .env file."""
    try:
        import streamlit as st

        if "GROQ_API_KEY" in st.secrets:
            return str(st.secrets["GROQ_API_KEY"]).strip() or None
    except Exception:
        pass
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass
    key = os.getenv("GROQ_API_KEY", "").strip()
    return key or None


def _extra(model: str) -> dict:
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low", "include_reasoning": False}
    if model.startswith("qwen/"):
        return {"reasoning_format": "hidden"}
    return {}


@dataclass
class Call:
    text: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    cached: bool = False


class Client:
    def __init__(self, key: str | None = None, cache: str | Path | None = None, retries: int = 6):
        self._key, self._groq, self._retries = key, None, retries
        self.cache_path = Path(cache) if cache else None
        self.cache: dict[str, dict] = {}
        if self.cache_path and self.cache_path.exists():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.cache[row["key"]] = row

    @property
    def groq(self):
        """The Groq client, created on first use: cached answers need no key."""
        if self._groq is None:
            from groq import Groq

            self._groq = Groq(api_key=self._key or api_key(), max_retries=self._retries)
        return self._groq

    def _hash(self, **parts) -> str:
        return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:24]

    def complete(self, model: str, system: str, user: str, *, schema: dict | None = None,
                 temperature: float = 0.0, max_tokens: int = 900, tag: str = "") -> Call:
        key = self._hash(model=model, system=system, user=user, schema=bool(schema), t=temperature, tag=tag)
        if key in self.cache:
            r = self.cache[key]
            return Call(r["text"], r["prompt_tokens"], r["completion_tokens"], r["seconds"], cached=True)
        kwargs = dict(model=model, temperature=temperature, max_tokens=max_tokens,
                      messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        if schema:
            kwargs["response_format"] = {"type": "json_schema",
                                         "json_schema": {"name": "answer", "schema": schema, "strict": True}}
        start = time.perf_counter()
        try:
            resp = self.groq.chat.completions.create(**kwargs, extra_body=_extra(model) or None)
        except Exception as err:   # some models only accept plain JSON mode
            failed = _failed_generation(err)
            if failed is not None:   # the model's JSON broke the schema: keep it as an invalid answer, don't crash
                return self._store(key, model, tag, Call(failed, 0, 0, round(time.perf_counter() - start, 3)))
            if schema and "json_schema" in str(err):
                kwargs["response_format"] = {"type": "json_object"}
                kwargs["messages"][0]["content"] += ("\n\nReturn only the JSON object, matching this schema:\n"
                                                     + json.dumps(schema))
                resp = self.groq.chat.completions.create(**kwargs, extra_body=_extra(model) or None)
            else:
                raise
        call = Call(resp.choices[0].message.content or "", resp.usage.prompt_tokens, resp.usage.completion_tokens,
                    round(time.perf_counter() - start, 3))
        return self._store(key, model, tag, call)

    def _store(self, key: str, model: str, tag: str, call: Call) -> Call:
        if self.cache_path is not None:
            row = {"key": key, "model": model, "tag": tag, **call.__dict__}
            row.pop("cached")
            self.cache[key] = row
            with self.cache_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        return call

    def structured(self, model: str, system: str, user: str, schema: dict, parse, tag: str = "",
                   max_tokens: int = 900):
        """A JSON answer in a strict schema, validated by `parse` (a pydantic model's model_validate_json).
        Returns (object or None, call, error message)."""
        call = self.complete(model, system, user, schema=schema, tag=tag, max_tokens=max_tokens)
        try:
            return parse(_json_part(call.text)), call, ""
        except (ValidationError, ValueError) as err:
            return None, call, str(err).splitlines()[0]


def _failed_generation(err: Exception) -> str | None:
    """Groq rejects strict-schema output that breaks the schema (400, json_validate_failed) and returns what the model
    wrote; that text is the model's answer, invalid."""
    body = getattr(err, "body", None)
    body = body.get("error", body) if isinstance(body, dict) else None
    if isinstance(body, dict) and body.get("code") == "json_validate_failed":
        return str(body.get("failed_generation") or "")
    return None


def _json_part(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object in the reply")
    return text[start:end + 1]
