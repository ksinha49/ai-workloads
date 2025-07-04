import importlib.util
import json
import sys


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_fake_send(calls):
    class FakeSQS:
        def send_message(self, QueueUrl=None, MessageBody=None):
            calls.append(json.loads(MessageBody))
            return {"MessageId": "1"}

    return FakeSQS()


def test_choose_backend(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")
    monkeypatch.setenv("CLASSIFIER_MODEL_ID", "x")
    module = load_lambda("router_app", "services/llm-router/router-lambda/app.py")
    monkeypatch.setattr(
        module,
        "invoke_classifier",
        lambda client, model, prompt: "complex" if len(prompt.split()) > 3 else "simple",
    )
    assert module._choose_backend("a b") == "ollama"
    assert module._choose_backend("a b c d") == "bedrock"


def test_lambda_handler(monkeypatch):
    monkeypatch.setenv("INVOCATION_QUEUE_URL", "url")
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")

    calls = []
    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: _make_fake_send(calls))
    module = load_lambda("router_lambda", "services/llm-router/router-lambda/app.py")
    module.sqs_client = sys.modules["boto3"].client("sqs")

    event1 = {"body": json.dumps({"prompt": "short"})}
    out1 = module.lambda_handler(event1, {})
    body1 = json.loads(out1["body"])
    assert body1["backend"] == "ollama"
    assert calls[0]["backend"] == "ollama"

    event2 = {"body": json.dumps({"prompt": "one two three four"})}
    out2 = module.lambda_handler(event2, {})
    body2 = json.loads(out2["body"])
    assert body2["backend"] == "bedrock"
    assert calls[1]["backend"] == "bedrock"


def test_lambda_handler_backend_override(monkeypatch):
    monkeypatch.setenv("INVOCATION_QUEUE_URL", "url")
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")

    calls = []
    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: _make_fake_send(calls))
    module = load_lambda("router_lambda_override", "services/llm-router/router-lambda/app.py")
    module.sqs_client = sys.modules["boto3"].client("sqs")

    event = {"body": json.dumps({"prompt": "short", "backend": "bedrock"})}
    out = module.lambda_handler(event, {})
    body = json.loads(out["body"])
    assert body["backend"] == "bedrock"
    assert calls[0]["backend"] == "bedrock"

    event2 = {"body": json.dumps({"prompt": "one two three four", "backend": "ollama"})}
    out2 = module.lambda_handler(event2, {})
    body2 = json.loads(out2["body"])
    assert body2["backend"] == "ollama"
    assert calls[1]["backend"] == "ollama"


def test_lambda_handler_strategy(monkeypatch):
    monkeypatch.setenv("INVOCATION_QUEUE_URL", "url")
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")

    calls = []
    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: _make_fake_send(calls))
    module = load_lambda("router_lambda_strategy", "services/llm-router/router-lambda/app.py")
    module.sqs_client = sys.modules["boto3"].client("sqs")

    event = {"body": json.dumps({"prompt": "short", "strategy": "complexity"})}
    out = module.lambda_handler(event, {})
    body = json.loads(out["body"])
    assert body["backend"] == "ollama"
    assert calls[0]["backend"] == "ollama"


def test_lambda_handler_invoke_error(monkeypatch):
    monkeypatch.setenv("INVOCATION_QUEUE_URL", "url")
    monkeypatch.setenv("PROMPT_COMPLEXITY_THRESHOLD", "3")

    class ErrorLambda:
        def send_message(self, QueueUrl=None, MessageBody=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: ErrorLambda())
    module = load_lambda("router_lambda_error", "services/llm-router/router-lambda/app.py")
    module.sqs_client = sys.modules["boto3"].client("sqs")

    event = {"body": json.dumps({"prompt": "short"})}
    out = module.lambda_handler(event, {})
    body = json.loads(out["body"])
    assert out["statusCode"] == 500
    assert "boom" in body["error"]


def test_lambda_handler_malicious_prompt(monkeypatch):
    monkeypatch.setenv("INVOCATION_QUEUE_URL", "url")
    calls = []
    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: _make_fake_send(calls))
    module = load_lambda("router_lambda_malicious", "services/llm-router/router-lambda/app.py")
    module.sqs_client = sys.modules["boto3"].client("sqs")

    event = {"body": json.dumps({"prompt": "<script>alert('x')</script>"})}
    out = module.lambda_handler(event, {})
    assert out["statusCode"] == 202
    queued = calls[0]
    assert "<" not in queued["prompt"]
    assert ">" not in queued["prompt"]
    assert "'" not in queued["prompt"]
    assert '"' not in queued["prompt"]


def test_lambda_handler_bad_prompt_type(monkeypatch):
    monkeypatch.setenv("INVOCATION_QUEUE_URL", "url")
    calls = []
    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: _make_fake_send(calls))
    module = load_lambda("router_lambda_bad", "services/llm-router/router-lambda/app.py")
    module.sqs_client = sys.modules["boto3"].client("sqs")

    event = {"body": json.dumps({"prompt": ["bad"]})}
    out = module.lambda_handler(event, {})
    assert out["statusCode"] == 400

