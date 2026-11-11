"""Traductor por suscripción de Claude (CLI `claude -p`), probado con un binario falso."""
import json
import stat
import sys

import pytest

from app.pipeline.translate import ClaudeCLITranslator, FatalAPIError


def fake_cli(tmp_path, body: str):
    """Crea un ejecutable 'claude' falso que guarda argv/env/stdin y ejecuta `body` (Python)."""
    log = tmp_path / "calls.jsonl"
    script = tmp_path / "claude"
    script.write_text(f"""#!{sys.executable}
import json, os, sys
stdin = sys.stdin.read()
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps({{"argv": sys.argv[1:], "stdin": stdin, "cwd": os.getcwd(),
                         "keys": [k for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN") if k in os.environ]}}) + "\\n")
{body}
""")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script, log


def calls(log):
    return [json.loads(line) for line in log.read_text().splitlines()]


OK = """
req = json.loads(stdin.split("\\n", 1)[1])
segs = [{"id": s["id"], "translation": "ES:" + s["text"]} for s in req["segments"]]
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "",
                  "structured_output": {"segments": segs}}))
"""


def test_translate_batch_isolated_call(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok")
    script, log = fake_cli(tmp_path, OK)
    tr = ClaudeCLITranslator(model="sonnet", binary=str(script))
    out = tr.translate_batch([{"id": "a", "type": "body", "text": "The Sun"}], {"title": "T", "glossary": {}})
    assert out["a"]["translation"] == "ES:The Sun"
    call = calls(log)[0]
    argv = call["argv"]
    assert argv[:3] == ["-p", "--model", "sonnet"]
    for flag in ("--strict-mcp-config", "--no-session-persistence", "--disable-slash-commands", "--json-schema"):
        assert flag in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert json.loads(argv[argv.index("--settings") + 1]) == {"autoMemoryEnabled": False}
    assert "traductor editorial" in argv[argv.index("--system-prompt") + 1]
    assert call["keys"] == []  # sin llaves de API: se usa la suscripción
    assert "claude-call-" in call["cwd"]
    assert tr.model == "claude-sonnet"


def test_result_text_fallback(tmp_path):
    script, _ = fake_cli(tmp_path, """
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "result": "```json\\n{\\"names\\": [{\\"text\\": \\"Carole Taylor\\", \\"type\\": \\"NAME\\"}]}\\n```"}))
""")
    names = ClaudeCLITranslator(binary=str(script)).extract_names("Carole Taylor")
    assert names == [{"text": "Carole Taylor", "type": "NAME"}]


def test_quota_is_fatal(tmp_path):
    script, log = fake_cli(tmp_path, """
print(json.dumps({"type": "result", "subtype": "success", "is_error": True,
                  "result": "You've hit your session limit · resets 5pm"}))
sys.exit(1)
""")
    with pytest.raises(FatalAPIError, match="CLAUDE_QUOTA"):
        ClaudeCLITranslator(binary=str(script)).translate_batch([{"id": "a", "type": "body", "text": "x"}], {})
    assert len(calls(log)) == 1  # la cuota no se reintenta


def test_login_and_missing_binary(tmp_path):
    script, _ = fake_cli(tmp_path, """
print(json.dumps({"type": "result", "is_error": True, "result": "Not logged in · Please run /login"}))
sys.exit(1)
""")
    with pytest.raises(FatalAPIError, match="CLAUDE_LOGIN"):
        ClaudeCLITranslator(binary=str(script)).extract_names("x")
    with pytest.raises(FatalAPIError, match="CLAUDE_CLI_MISSING"):
        ClaudeCLITranslator(binary=str(tmp_path / "nope")).extract_names("x")


def test_transient_error_retried(tmp_path, monkeypatch):
    import app.pipeline.translate as t

    monkeypatch.setattr(t.ClaudeCLITranslator._chat_json.retry, "sleep", lambda s: None)
    flag = tmp_path / "failed_once"
    script, log = fake_cli(tmp_path, f"""
import pathlib
flag = pathlib.Path({str(flag)!r})
if not flag.exists():
    flag.write_text("1")
    print("boom", file=sys.stderr)
    sys.exit(1)
""" + OK)
    out = ClaudeCLITranslator(binary=str(script)).translate_batch([{"id": "a", "type": "body", "text": "x"}], {})
    assert out["a"]["translation"] == "ES:x"
    assert len(calls(log)) == 2
