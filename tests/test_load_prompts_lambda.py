import importlib.util
import sys
import json


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_prompts(monkeypatch):
    monkeypatch.setenv("PROMPT_ENGINE_ENDPOINT", "http://engine")
    sent = {}

    class Resp:
        def raise_for_status(self):
            pass
        def json(self):
            return [{"query": "q"}]

    def fake_post(url, json=None):
        sent["url"] = url
        sent["json"] = json
        return Resp()

    monkeypatch.setattr(sys.modules["httpx"], "post", fake_post)

    module = load_lambda("load", "services/summarization/load-prompts-lambda/app.py")
    out = module.lambda_handler({"workflow_id": "aps"}, {})
    assert sent == {"url": "http://engine", "json": {"workflow_id": "aps"}}
    assert out["prompts"] == [{"query": "q"}]
