import importlib.util
import json
import sys


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_fake_invoke(calls):
    class FakePayload:
        def __init__(self, data):
            self._data = data

        def read(self):
            return json.dumps(self._data).encode("utf-8")

    class FakeLambda:
        def invoke(self, FunctionName=None, Payload=None):
            data = json.loads(Payload)
            calls.append((FunctionName, data))
            reply = {"reply": "bedrock" if data.get("backend") == "bedrock" else "ollama"}
            return {"Payload": FakePayload(reply)}

    return FakeLambda()


def test_choose_backend(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")
    module = load_lambda("router_app", "services/llm-router/router-lambda/app.py")
    assert module._choose_backend("a b") == "ollama"
    assert module._choose_backend("a b c d") == "bedrock"


def test_lambda_handler(monkeypatch):
    monkeypatch.setenv("LLM_INVOCATION_FUNCTION", "invoke")
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")

    calls = []
    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: _make_fake_invoke(calls))
    module = load_lambda("router_lambda", "services/llm-router/router-lambda/app.py")
    module.lambda_client = sys.modules["boto3"].client("lambda")

    event1 = {"body": json.dumps({"prompt": "short"})}
    out1 = module.lambda_handler(event1, {})
    body1 = json.loads(out1["body"])
    assert body1["backend"] == "ollama"
    assert calls[0][1]["backend"] == "ollama"

    event2 = {"body": json.dumps({"prompt": "one two three four"})}
    out2 = module.lambda_handler(event2, {})
    body2 = json.loads(out2["body"])
    assert body2["backend"] == "bedrock"
    assert calls[1][1]["backend"] == "bedrock"


def test_lambda_handler_backend_override(monkeypatch):
    monkeypatch.setenv("LLM_INVOCATION_FUNCTION", "invoke")
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")

    calls = []
    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: _make_fake_invoke(calls))
    module = load_lambda("router_lambda_override", "services/llm-router/router-lambda/app.py")
    module.lambda_client = sys.modules["boto3"].client("lambda")

    event = {"body": json.dumps({"prompt": "short", "backend": "bedrock"})}
    out = module.lambda_handler(event, {})
    body = json.loads(out["body"])
    assert body["backend"] == "bedrock"
    assert calls[0][1]["backend"] == "bedrock"

    event2 = {"body": json.dumps({"prompt": "one two three four", "backend": "ollama"})}
    out2 = module.lambda_handler(event2, {})
    body2 = json.loads(out2["body"])
    assert body2["backend"] == "ollama"
    assert calls[1][1]["backend"] == "ollama"


def test_lambda_handler_strategy(monkeypatch):
    monkeypatch.setenv("LLM_INVOCATION_FUNCTION", "invoke")
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")

    calls = []
    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: _make_fake_invoke(calls))
    module = load_lambda("router_lambda_strategy", "services/llm-router/router-lambda/app.py")
    module.lambda_client = sys.modules["boto3"].client("lambda")

    event = {"body": json.dumps({"prompt": "short", "strategy": "complexity"})}
    out = module.lambda_handler(event, {})
    body = json.loads(out["body"])
    assert body["backend"] == "ollama"
    assert calls[0][1]["backend"] == "ollama"
