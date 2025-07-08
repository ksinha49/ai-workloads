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
    monkeypatch.setenv("SYSTEM_WORKFLOW_ID", "sys")
    monkeypatch.setattr(
        "common_utils.get_ssm.get_config",
        lambda name, **_: None,
    )
    sent = []

    class Resp:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self._data

    def fake_post(url, json=None):
        sent.append({"url": url, "json": json})
        if json.get("workflow_id") == "aps":
            return Resp([{"query": "q"}])
        else:
            return Resp([{"template": "s"}])


    monkeypatch.setattr(sys.modules["httpx"], "post", fake_post)

    module = load_lambda("load", "services/summarization/src/load_prompts_lambda.py")
    out = module.lambda_handler({"workflow_id": "aps"}, {})
    assert sent == [
        {"url": "http://engine", "json": {"workflow_id": "aps"}},
        {"url": "http://engine", "json": {"workflow_id": "sys"}},
    ]
    assert out == {
        "prompts": [{"query": "q"}],
        "llm_params": {"system_prompt": "s"},
    }