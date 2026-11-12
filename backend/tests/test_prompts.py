"""Prompts: registro de solo lectura, sobrescritura en el playground y medidor de uso."""
import hashlib
import json

import httpx
import pytest

from app.pipeline import translate as tr
from tests.test_claude_translator import OK, calls, fake_cli

# texto exacto de producción antes del cambio a {lang} con llaves simples (la caché c2 depende de él)
CORRECT_HASHES = {
    "en": "b13068c2badc1dd75414192f2bbbc82682189a302a90301c5f76ae157c3bafed",
    "es": "76555f6d73a02bb2a08b8c9950ed4873716f2c689afa92c7cf6781a8bcedb298",
    "auto": "ff93c9725bd8aa7561b96c25b1d75f460a4635044b05fedfc00e5c6fc654ae26",
}


def test_correct_prompt_rendering_unchanged():
    for lang, digest in CORRECT_HASHES.items():
        text = tr.render_correct(tr.CORRECT_PROMPT, lang)
        assert hashlib.sha256(text.encode()).hexdigest() == digest
    # un borrador sin {lang} se usa tal cual
    assert tr.render_correct("Corrige.", "en") == "Corrige."


def test_registry_lists_all_tasks():
    assert set(tr.PROMPTS) == {"translate", "correct", "shorten", "names"}
    assert tr.PROMPTS["translate"]["text"] == tr.SYSTEM_PROMPT
    assert tr.PROMPTS["translate"]["version"] == tr.PROMPT_VERSION
    assert tr.PROMPTS["correct"]["version"] == tr.CORRECT_PROMPT_VERSION
    for p in tr.PROMPTS.values():
        assert p["title"] and p["user_template"] and set(p["output"]) == {"deepseek", "claude"}
    json.dumps(tr.PROMPTS)  # serializable para la API


def deepseek_capture(monkeypatch, usage=None):
    sent = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        sent.append(body)
        segs = json.loads(body["messages"][1]["content"].split("\n", 1)[1])["segments"]
        content = json.dumps({"segments": [{"id": s["id"], "translation": "ES " + s["text"]} for s in segs]})
        data = {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
        if usage:
            data["usage"] = usage
        return httpx.Response(200, json=data)

    t = tr.DeepSeekTranslator("sk-test", "deepseek-flash")
    t._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://x")
    return t, sent


ITEMS = [{"id": "a", "type": "body", "text": "The Sun"}]


def test_deepseek_default_and_override_prompt(monkeypatch):
    t, sent = deepseek_capture(monkeypatch)
    t.translate_batch(ITEMS, {})
    assert sent[-1]["messages"][0]["content"] == tr.SYSTEM_PROMPT
    t.prompts = {"translate": "PROMPT BORRADOR"}
    t.translate_batch(ITEMS, {})
    assert sent[-1]["messages"][0]["content"] == "PROMPT BORRADOR"


def test_deepseek_meter_counts_tokens_cost_unknown(monkeypatch):
    t, _ = deepseek_capture(monkeypatch, usage={"prompt_tokens": 100, "completion_tokens": 40})
    t.meter = tr.UsageMeter()
    t.translate_batch(ITEMS, {})
    t.translate_batch(ITEMS, {})
    m = t.meter.snapshot()
    assert m == {"calls": 2, "tokens_in": 200, "tokens_out": 80, "cost_usd": None}


def test_claude_override_prompt_and_meter(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    body = OK.replace('"structured_output"', '"usage": {"input_tokens": 50, "output_tokens": 7}, '
                                              '"total_cost_usd": 0.0125, "structured_output"')
    script, log = fake_cli(tmp_path, body)
    t = tr.ClaudeCLITranslator(binary=str(script), prompts={"translate": "BORRADOR CLAUDE"})
    t.meter = tr.UsageMeter()
    t.translate_batch(ITEMS, {})
    argv = calls(log)[0]["argv"]
    assert argv[argv.index("--system-prompt") + 1] == "BORRADOR CLAUDE"
    assert t.meter.snapshot() == {"calls": 1, "tokens_in": 50, "tokens_out": 7, "cost_usd": 0.0125}


def test_correct_override_renders_lang(tmp_path, monkeypatch):
    t, sent = deepseek_capture(monkeypatch)
    t._client = httpx.Client(transport=httpx.MockTransport(lambda r: (sent.append(json.loads(r.content)), httpx.Response(
        200, json={"choices": [{"message": {"content": '{"segments": []}'}, "finish_reason": "stop"}]}))[1]),
        base_url="https://x")
    t.prompts = {"correct": "Libro en {lang}."}
    t.correct_batch([{"id": "a", "text": "x"}], {"lang": "es"})
    assert sent[-1]["messages"][0]["content"] == "Libro en español."


def test_meter_is_thread_safe():
    from concurrent.futures import ThreadPoolExecutor

    m = tr.UsageMeter()
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda _: m.add(tokens_in=1, tokens_out=2, cost_usd=0.5), range(400)))
    s = m.snapshot()
    assert s["calls"] == 400 and s["tokens_in"] == 400 and s["tokens_out"] == 800 and s["cost_usd"] == pytest.approx(200)
