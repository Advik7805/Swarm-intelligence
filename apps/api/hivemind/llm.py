"""Single OpenAI-compatible LLM entry point.

Precedence: OLLAMA_BASE_URL → configured LLM_BASE_URL + key → DEMO MODE
(returns None; every caller has a deterministic offline fallback, so the
whole platform runs end-to-end with zero external calls).
"""
import json
from typing import Any

from openai import OpenAI

from .config import get_settings

_client: OpenAI | None = None


def _get_client() -> tuple[OpenAI, str] | None:
    global _client
    s = get_settings()
    if s.is_demo:
        return None
    if _client is None:
        if s.ollama_base_url:
            _client = OpenAI(base_url=s.ollama_base_url, api_key="ollama")
            _model = s.ollama_model or "llama3.1"
        else:
            base = s.llm_base_url or "https://api.openai.com/v1"
            _client = OpenAI(base_url=base, api_key=s.llm_api_key)
            _model = s.llm_model_name or "gpt-4o-mini"
        _client._hivemind_model = _model  # type: ignore[attr-defined]
    return _client, _client._hivemind_model  # type: ignore[attr-defined]


def complete(system: str, user: str, max_tokens: int = 600) -> str | None:
    client = _get_client()
    if client is None:
        return None
    cli, model = client
    try:
        resp = cli.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.8,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:  # never hard-crash a simulation on LLM failure
        print(f"[llm] call failed, falling back to demo: {e}")
        return None


def complete_json(system: str, user: str, max_tokens: int = 1600) -> dict[str, Any] | None:
    client = _get_client()
    if client is None:
        return None
    cli, model = client
    try:
        resp = cli.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system + "\nRespond with strict JSON only."},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        print(f"[llm] json call failed, falling back to demo: {e}")
        try:
            resp = cli.chat.completions.create(  # retry without json mode
                model=model,
                messages=[
                    {"role": "system", "content": system + "\nRespond with strict JSON only."},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.4,
            )
            text = (resp.choices[0].message.content or "").strip()
            return json.loads(text[text.index("{"): text.rindex("}") + 1])
        except Exception:
            return None


def mode() -> str:
    return "demo" if get_settings().is_demo else "live"
