import importlib.util
import json
import io


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
    monkeypatch.setattr(boto3, 'client', lambda name: FakeSFN())
    module = load_lambda('ingest', 'services/knowledge-base/ingest-lambda/app.py')
    module.sfn = FakeSFN()
    module.STATE_MACHINE_ARN = 'arn'
    out = module.lambda_handler({'text': 't', 'docType': 'pdf', 'department': 'HR'}, {})
    assert out['started'] is True
    assert calls['arn'] == 'arn'
    assert calls['input']['text'] == 't'
    assert calls['input']['docType'] == 'pdf'
    assert calls['input']['metadata']['department'] == 'HR'


def test_kb_query(monkeypatch):
    import boto3
    class FakeLambda:
        def invoke(self, FunctionName=None, Payload=None):
            assert FunctionName == 'arn'
            body = json.loads(Payload)
            return {'Payload': io.BytesIO(json.dumps({'result': body}).encode())}
    monkeypatch.setattr(boto3, 'client', lambda name: FakeLambda())
    module = load_lambda('query', 'services/knowledge-base/query-lambda/app.py')
    module.lambda_client = FakeLambda()
    module.SUMMARY_FUNCTION_ARN = 'arn'
    out = module.lambda_handler({'query': 'hi', 'team': 'x'}, {})
    assert out['result']['team'] == 'x'
