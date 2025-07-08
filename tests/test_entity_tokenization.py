import importlib.util
import hashlib
import sys
import types


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTable:
    def __init__(self, items=None):
        self.items = items or []

    def scan(self):
        return {"Items": list(self.items)}

    def put_item(self, Item=None):
        self.items.append(Item)
        return {}


class FakeResource:
    def __init__(self, table):
        self._table = table

    def Table(self, name):
        return self._table


def test_generate_token(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(sys.modules['boto3'], 'resource', lambda name: FakeResource(table), raising=False)
    monkeypatch.setenv('TOKEN_TABLE', 'tbl')
    monkeypatch.setenv('TOKEN_PREFIX', 'tok-')
    monkeypatch.setenv('TOKEN_SALT', 's')
    module = load_lambda('tokenize', 'services/anonymization/src/tokenize_entities_lambda.py')
    out = module.lambda_handler({'entity': 'Bob', 'entity_type': 'NAME', 'domain': 'gen'}, {})
    expected = 'tok-' + hashlib.blake2b('sBob'.encode(), digest_size=4).hexdigest()
    assert out['token'] == expected
    assert table.items[0]['entity'] == 'Bob'


def test_existing_token(monkeypatch):
    existing = {'token': 'tok-1234', 'entity': 'Bob', 'entity_type': 'NAME', 'domain': 'gen'}
    table = FakeTable([existing])
    monkeypatch.setattr(sys.modules['boto3'], 'resource', lambda name: FakeResource(table), raising=False)
    monkeypatch.setenv('TOKEN_TABLE', 'tbl')
    monkeypatch.setenv('TOKEN_PREFIX', 'tok-')
    monkeypatch.delenv('TOKEN_SALT', raising=False)
    module = load_lambda('tokenize2', 'services/anonymization/src/tokenize_entities_lambda.py')
    out = module.lambda_handler({'entity': 'Bob', 'entity_type': 'NAME', 'domain': 'gen'}, {})
    assert out['token'] == 'tok-1234'
    assert len(table.items) == 1


def test_uuid_generation(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(sys.modules['boto3'], 'resource', lambda name: FakeResource(table), raising=False)
    monkeypatch.setenv('TOKEN_TABLE', 'tbl')
    monkeypatch.setenv('TOKEN_PREFIX', 'pre_')
    monkeypatch.delenv('TOKEN_SALT', raising=False)
    module = load_lambda('tokenize3', 'services/anonymization/src/tokenize_entities_lambda.py')
    out = module.lambda_handler({'entity': 'A', 'entity_type': 'TYPE', 'domain': ''}, {})
    assert out['token'].startswith('pre_')
    assert len(out['token']) == len('pre_') + 8
