import importlib.util
import json
import sys


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_starts_state_machine(monkeypatch):
    monkeypatch.setenv("STATE_MACHINE_ARN", "arn")

    started = {}

    class FakeSF:
        def start_execution(self, stateMachineArn=None, input=None):
            started["arn"] = stateMachineArn
            started["input"] = json.loads(input)

    class FakeSQS:
        def receive_message(self, **kwargs):
            return {}
        def delete_message(self, **kwargs):
            pass

    import boto3
    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: FakeSF() if name == "stepfunctions" else FakeSQS())

    module = load_lambda("worker", "services/rag-ingestion-worker/worker-lambda/app.py")
    event = {"Records": [{"body": json.dumps({"text": "t", "collection_name": "c"})}]}
    module.lambda_handler(event, {})

    assert started["arn"] == "arn"
    assert started["input"]["text"] == "t"
