import importlib.util
import datetime
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'common', 'layers', 'common-utils', 'python'))


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cleanup_lambda(monkeypatch, s3_stub):
    monkeypatch.setenv('CLEANUP_BUCKETS', 'b')
    monkeypatch.setenv('DELETE_AFTER_DAYS', '1')
    monkeypatch.setattr('common_utils.get_ssm.get_config', lambda name, **_: None)
    module = load_lambda('cleanup', 'services/file-ingestion/pending-delete-cleanup-lambda/app.py')
    now = datetime.datetime.utcnow()
    s3_stub.put_object(Bucket='b', Key='old.txt', Body=b'data')
    s3_stub.tags[('b', 'old.txt')] = {'pending-delete': 'true'}
    s3_stub.last_modified[('b', 'old.txt')] = now - datetime.timedelta(days=2)

    s3_stub.put_object(Bucket='b', Key='new.txt', Body=b'data')
    s3_stub.tags[('b', 'new.txt')] = {'pending-delete': 'true'}
    s3_stub.last_modified[('b', 'new.txt')] = now

    s3_stub.put_object(Bucket='b', Key='untagged.txt', Body=b'data')
    s3_stub.last_modified[('b', 'untagged.txt')] = now - datetime.timedelta(days=2)

    monkeypatch.setattr(module, '_s3', s3_stub)

    result = module.lambda_handler({}, {})
    assert ('b', 'old.txt') not in s3_stub.objects
    assert ('b', 'new.txt') in s3_stub.objects
    assert ('b', 'untagged.txt') in s3_stub.objects
    assert result['deleted'] == 1
