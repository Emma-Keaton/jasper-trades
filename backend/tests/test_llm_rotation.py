"""Groq key rotation: round-robin, 429 cooldown, all-cooling wait, client rotation."""
from types import SimpleNamespace

import pytest

from app.services.llm_service import GroqKeyRotator, GroqLLMClient, _parse_keys

JSON_REPLY = '{"ok": true}'


class FakeCompletions:
    def __init__(self, api_key):
        self._api_key = api_key

    async def create(self, **kwargs):
        if self._api_key == "key-fail" or "fail" in self._api_key:
            raise RuntimeError("429 rate limit exceeded")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=JSON_REPLY))]
        )


class FakeOpenAI:
    """Stand-in for `openai.AsyncOpenAI`.

    `default_headers` is part of the real signature (the Groq client sends
    `_GROQ_HEADERS`), so the stub must accept it even though it ignores it.
    """

    def __init__(self, base_url=None, api_key=None, default_headers=None):
        self.base_url = base_url
        self.default_headers = default_headers
        self.chat = SimpleNamespace(completions=FakeCompletions(api_key))


# ---------------------------------------------------------------------------
# GroqKeyRotator
# ---------------------------------------------------------------------------

def test_parse_keys():
    assert _parse_keys(None) == []
    assert _parse_keys("") == []
    assert _parse_keys("a,b") == ["a", "b"]
    assert _parse_keys("a\nb, c ") == ["a", "b", "c"]


def test_rotator_requires_keys():
    with pytest.raises(ValueError):
        GroqKeyRotator([])


async def test_rotator_round_robin():
    rot = GroqKeyRotator(["key-a", "key-b"])
    first = await rot.acquire()
    second = await rot.acquire()
    third = await rot.acquire()
    assert first.api_key in ("key-a", "key-b")
    assert first.api_key != second.api_key
    assert third.api_key == first.api_key


async def test_rate_limited_key_is_skipped():
    rot = GroqKeyRotator(["key-a", "key-b"])
    first = await rot.acquire()
    rot.mark_rate_limited(first, retry_after=60)
    second = await rot.acquire()
    assert second.api_key != first.api_key


async def test_rate_limit_increments_consecutive_429s():
    rot = GroqKeyRotator(["key-a"])
    state = await rot.acquire()
    rot.mark_rate_limited(state, retry_after=10)
    assert state.consecutive_429s == 1
    rot.mark_rate_limited(state, retry_after=10)
    assert state.consecutive_429s == 2


async def test_mark_success_resets_consecutive_429s():
    rot = GroqKeyRotator(["key-a"])
    state = await rot.acquire()
    rot.mark_rate_limited(state, retry_after=10)
    rot.mark_success(state)
    assert state.consecutive_429s == 0


async def test_all_cooling_waits_then_rotates():
    rot = GroqKeyRotator(["key-a", "key-b"])
    s1 = await rot.acquire()
    s2 = await rot.acquire()
    rot.mark_rate_limited(s1, retry_after=0.01)
    rot.mark_rate_limited(s2, retry_after=0.01)
    s3 = await rot.acquire()
    assert s3.api_key in ("key-a", "key-b")


# ---------------------------------------------------------------------------
# GroqLLMClient
# ---------------------------------------------------------------------------

async def test_chat_completion_rotates_on_429(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.AsyncOpenAI", FakeOpenAI)
    client = GroqLLMClient(keys=["key-good", "key-fail"])
    assert client.is_configured
    text = await client.chat_completion(
        [{"role": "user", "content": "hi"}], task_type="analysis"
    )
    assert text == JSON_REPLY


async def test_chat_completion_raises_when_all_fail(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.AsyncOpenAI", FakeOpenAI)
    client = GroqLLMClient(keys=["key-fail", "key-fail"])
    with pytest.raises(RuntimeError, match="429"):
        await client.chat_completion([{"role": "user", "content": "hi"}])
    # Both keys should now be cooling down.
    statuses = client.rotator.status()
    assert len(statuses) == 2
    assert all(s["cooling_down"] for s in statuses)


async def test_structured_output_parses_json(monkeypatch):
    monkeypatch.setattr("app.services.llm_service.AsyncOpenAI", FakeOpenAI)
    client = GroqLLMClient(keys=["key-good", "key-fail"])
    result = await client.structured_output(
        [{"role": "user", "content": "analyze"}], {"ok": "boolean"}
    )
    assert result == {"ok": True}


async def test_structured_output_falls_back_to_empty_on_non_json(monkeypatch):
    class TextCompletions:
        async def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="no json here"))]
            )

    class TextOpenAI:
        def __init__(self, base_url=None, api_key=None, default_headers=None):
            self.chat = SimpleNamespace(completions=TextCompletions())

    monkeypatch.setattr("app.services.llm_service.AsyncOpenAI", TextOpenAI)
    client = GroqLLMClient(keys=["key-good"])
    result = await client.structured_output(
        [{"role": "user", "content": "analyze"}], {"ok": "boolean"}
    )
    assert result == {}


def test_unconfigured_client_when_no_keys(monkeypatch):
    from app.services import llm_service

    # Settings field names are upper-case; `Groq_API_KEY`/`Groq_API_KEYS` never
    # existed and monkeypatching them raised AttributeError instead of clearing
    # the keys, so this test could not test what it claimed.
    monkeypatch.setattr(llm_service.settings, "GROQ_API_KEY", None)
    monkeypatch.setattr(llm_service.settings, "GROQ_API_KEYS", None)
    client = GroqLLMClient(keys=[])
    assert client.is_configured is False
    assert client.rotator is None
