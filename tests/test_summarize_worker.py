import importlib.util
import sys
import io
import json


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_prompt_engine(monkeypatch):
    monkeypatch.setenv("RAG_SUMMARY_FUNCTION_ARN", "arn")
    monkeypatch.setenv("PROMPT_ENGINE_ENDPOINT", "http://engine")

    invoked = {}
    success = {}

    class FakeLambda:
        def invoke(self, FunctionName=None, Payload=None):
            invoked["payload"] = json.loads(Payload.decode())
            data = {"result": "sum"}
            return {"Payload": io.BytesIO(json.dumps(data).encode())}

    class FakeSF:
        def send_task_success(self, taskToken=None, output=None):
            success["output"] = json.loads(output)

    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: FakeLambda() if name == "lambda" else FakeSF())

    posted = {}

    class Resp:
        def raise_for_status(self):
            pass

    def fake_post(url, json=None):
        posted["url"] = url
        posted["json"] = json
        return Resp()

    monkeypatch.setattr(sys.modules["httpx"], "post", fake_post)

    module = load_lambda("worker", "services/summarization/src/summarize_worker_lambda.py")
    event = {
        "Records": [
            {
                "body": json.dumps(
                    {
                        "token": "tok",
                        "query": "q",
                        "collection_name": "c",
                        "file_guid": "g",
                        "document_id": "d",
                        "Title": "T",
                        "prompt_id": "p1",
                        "variables": {"a": 1},
                    }
                )
            }
        ]
    }
    module.lambda_handler(event, {})

    assert posted == {"url": "http://engine", "json": {"prompt_id": "p1", "variables": {"a": 1}}}
    assert invoked["payload"]["collection_name"] == "c"
    assert invoked["payload"]["file_guid"] == "g"
    assert invoked["payload"]["document_id"] == "d"
    assert success["output"]["summary"] == "sum"
    assert success["output"]["file_guid"] == "g"
    assert success["output"]["document_id"] == "d"


def test_worker_legacy_fallback(monkeypatch):
    monkeypatch.setenv("RAG_SUMMARY_FUNCTION_ARN", "arn")

    invoked = {}
    success = {}

    class FakeLambda:
        def invoke(self, FunctionName=None, Payload=None):
            invoked["payload"] = json.loads(Payload.decode())
            data = {"summary": {"choices": [{"message": {"content": "old"}}]}}
            return {"Payload": io.BytesIO(json.dumps(data).encode())}

    class FakeSF:
        def send_task_success(self, taskToken=None, output=None):
            success["output"] = json.loads(output)

    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: FakeLambda() if name == "lambda" else FakeSF())

    module = load_lambda("worker_fallback", "services/summarization/src/summarize_worker_lambda.py")
    event = {"Records": [{"body": json.dumps({"token": "tok", "query": "q", "collection_name": "c"})}]}

    module.lambda_handler(event, {})

    assert success["output"]["summary"] == "old"
