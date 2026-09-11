"""Chat model catalog — Qwen default + gpt-oss selectable via Ollama."""
from __future__ import annotations

from app import llm


def test_default_catalog_includes_qwen_and_gpt_oss():
    ids = {m["id"] for m in llm.DEFAULT_MODELS}
    assert "qwen2.5:7b-instruct" in ids
    assert "gpt-oss:20b" in ids


def test_llm_settings_resolves_active_qwen(monkeypatch, tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "llm:\n  model: qwen2.5:7b-instruct\n  base_url: http://127.0.0.1:11434\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(llm, "CONFIG_PATH", cfg)
    monkeypatch.setattr(llm, "load_config", lambda: {
        "llm": {"model": "qwen2.5:7b-instruct", "base_url": "http://127.0.0.1:11434"}
    })
    s = llm.llm_settings()
    assert s["model"] == "qwen2.5:7b-instruct"
    assert s["num_ctx"] == 4096


def test_llm_settings_gpt_oss_uses_smaller_ctx(monkeypatch):
    monkeypatch.setattr(llm, "load_config", lambda: {
        "llm": {"model": "gpt-oss:20b", "base_url": "http://127.0.0.1:11434"}
    })
    s = llm.llm_settings()
    assert s["model"] == "gpt-oss:20b"
    assert s["num_ctx"] == 2048
    assert s["num_thread"] >= 4


def test_set_active_model_writes_config(monkeypatch, tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("llm:\n  model: qwen2.5:7b-instruct\n  base_url: http://localhost:11434\n", encoding="utf-8")
    state = {"llm": {"model": "qwen2.5:7b-instruct", "base_url": "http://localhost:11434"}}

    def fake_load():
        return state

    def fake_write(c):
        state.clear()
        state.update(c)

    monkeypatch.setattr(llm, "CONFIG_PATH", cfg)
    monkeypatch.setattr(llm, "load_config", fake_load)
    monkeypatch.setattr(llm, "_write_config", fake_write)
    monkeypatch.setattr(llm, "unload_model", lambda *a, **k: None)
    monkeypatch.setattr(llm, "ollama_installed_names", lambda: ["qwen2.5:7b-instruct"])

    result = llm.set_active_model("gpt-oss:20b")
    assert result["model"] == "gpt-oss:20b"
    assert state["llm"]["model"] == "gpt-oss:20b"
    assert state["llm"]["path"] == "ollama://gpt-oss:20b"
    assert state["llm"]["num_ctx"] == 2048


def test_list_models_marks_active(monkeypatch):
    monkeypatch.setattr(llm, "load_config", lambda: {
        "llm": {"model": "qwen2.5:7b-instruct", "base_url": "http://localhost:11434"}
    })
    monkeypatch.setattr(llm, "ollama_installed_names", lambda: ["qwen2.5:7b-instruct"])
    rows = llm.list_models()
    active = [m for m in rows if m["active"]]
    assert len(active) == 1
    assert active[0]["id"] == "qwen2.5:7b-instruct"
    assert active[0]["installed"] is True
    oss = next(m for m in rows if m["id"] == "gpt-oss:20b")
    assert oss["installed"] is False
