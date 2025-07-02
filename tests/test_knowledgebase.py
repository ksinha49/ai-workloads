import importlib.util
import json
import io
import pytest
import sys
import types


def _stub_botocore(monkeypatch):
    botocore = types.ModuleType("botocore")
    exc_mod = types.ModuleType("botocore.exceptions")

    class ClientError(Exception):
        pass

    exc_mod.ClientError = ClientError
    botocore.exceptions = exc_mod
    monkeypatch.setitem(sys.modules, "botocore", botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", exc_mod)
    return ClientError


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kb_ingest(monkeypatch):
    calls = {}
    class FakeSFN:
        def start_execution(self, stateMachineArn=None, input=None):
            calls['arn'] = stateMachineArn
            calls['input'] = json.loads(input)
            return {}
    import boto3
    _stub_botocore(monkeypatch)
    monkeypatch.setattr(boto3, 'client', lambda name: FakeSFN())
    monkeypatch.setenv("STATE_MACHINE_ARN", "arn")
    module = load_lambda('ingest', 'services/knowledge-base/ingest-lambda/app.py')
    module.sfn = FakeSFN()
    out = module.lambda_handler({'text': 't', 'docType': 'pdf', 'department': 'HR'}, {})
    assert out['started'] is True
    assert calls['arn'] == 'arn'
    assert calls['input']['text'] == 't'
    assert calls['input']['docType'] == 'pdf'
    assert calls['input']['metadata']['department'] == 'HR'


def test_kb_ingest_missing_arn(monkeypatch):
    import boto3
    _stub_botocore(monkeypatch)

    class FakeSFN:
        pass

    monkeypatch.setattr(boto3, 'client', lambda name: FakeSFN())
    monkeypatch.delenv('STATE_MACHINE_ARN', raising=False)
    with pytest.raises(RuntimeError):
        load_lambda('ingest_noenv', 'services/knowledge-base/ingest-lambda/app.py')


def test_kb_ingest_error(monkeypatch):
    calls = {}

    class FakeSFN:
        def start_execution(self, stateMachineArn=None, input=None):
            calls['arn'] = stateMachineArn
            raise ClientError({'Error': {'Code': '400', 'Message': 'bad'}}, 'start_execution')

    import boto3
    ClientError = _stub_botocore(monkeypatch)
    monkeypatch.setattr(boto3, 'client', lambda name: FakeSFN())
    monkeypatch.setenv('STATE_MACHINE_ARN', 'arn')
    module = load_lambda('ingest_err', 'services/knowledge-base/ingest-lambda/app.py')
    module.sfn = FakeSFN()
    out = module.lambda_handler({'text': 't'}, {})
    assert out['started'] is False
    assert 'bad' in out['error']


def test_kb_query(monkeypatch):
    import boto3
    class FakeSQS:
        def send_message(self, QueueUrl=None, MessageBody=None):
            FakeSQS.body = json.loads(MessageBody)
            return {'MessageId': '1'}
    _stub_botocore(monkeypatch)
    monkeypatch.setattr(boto3, 'client', lambda name: FakeSQS())
    monkeypatch.setenv('SUMMARY_QUEUE_URL', 'url')
    module = load_lambda('query', 'services/knowledge-base/query-lambda/app.py')
    module.sqs_client = FakeSQS()
    out = module.lambda_handler({'query': 'hi', 'team': 'x'}, {})
    assert out['queued'] is True
    assert FakeSQS.body['team'] == 'x'


def test_kb_query_missing_arn(monkeypatch):
    import boto3
    _stub_botocore(monkeypatch)

    class FakeSQS:
        def send_message(self, QueueUrl=None, MessageBody=None):
            raise AssertionError("should not be called")

    monkeypatch.setattr(boto3, 'client', lambda name: FakeSQS())
    monkeypatch.delenv('SUMMARY_QUEUE_URL', raising=False)
    module = load_lambda('query_noenv', 'services/knowledge-base/query-lambda/app.py')
    module.sqs_client = FakeSQS()
    out = module.lambda_handler({'query': 'hi'}, {})
    assert 'SUMMARY_QUEUE_URL' in out['error']


def test_kb_query_error(monkeypatch):
    import boto3
    ClientError = _stub_botocore(monkeypatch)

    class FakeSQS:
        def send_message(self, QueueUrl=None, MessageBody=None):
            raise ClientError({'Error': {'Code': '400', 'Message': 'bad'}}, 'send')

    monkeypatch.setattr(boto3, 'client', lambda name: FakeSQS())
    monkeypatch.setenv('SUMMARY_QUEUE_URL', 'url')
    module = load_lambda('query_err', 'services/knowledge-base/query-lambda/app.py')
    module.sqs_client = FakeSQS()
    out = module.lambda_handler({'query': 'hi'}, {})
    assert 'bad' in out['error']
