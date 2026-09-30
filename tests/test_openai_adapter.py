import os
import pytest
from llm.client import OpenAIStructuredLLMClient

def test_openai_adapter_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # SDK may or may not be installed in test environment; either failure is explicit and safe.
    with pytest.raises(RuntimeError):
        OpenAIStructuredLLMClient()

def test_env_example_does_not_contain_secret():
    text=open(".env.example",encoding="utf-8").read()
    assert "OPENAI_API_KEY=" in text
    assert "sk-" not in text

def test_app_exposes_live_and_demo_modes():
    text=open("app.py",encoding="utf-8").read()
    assert "LIVE GPT" in text
    assert "DEMO offline" in text
    assert "OpenAIStructuredLLMClient" in text
