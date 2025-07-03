import importlib.util
import json
import urllib.request
import sys
import os
import pytest
import types
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'common', 'layers', 'common-utils', 'python'))

# Stub boto3.dynamodb.conditions.Attr used by the module
cond_mod = types.ModuleType("boto3.dynamodb.conditions")

class Attr:
    def __init__(self, name):
        self.name = name
    def eq(self, val):
        self.val = val
        return self

cond_mod.Attr = Attr
sys.modules.setdefault("boto3.dynamodb", types.ModuleType("boto3.dynamodb"))
sys.modules["boto3.dynamodb.conditions"] = cond_mod


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTable:
    def __init__(self, items=None):
        self.items = items or []

    def scan(self, *a, **k):
        return {"Items": self.items}

    def get_item(self, Key=None):
        for item in self.items:
            if item["id"] == Key["id"]:
                return {"Item": item}
        return {}


class FakeResource:
    def __init__(self, table):
        self._table = table

    def Table(self, name):
        return self._table


class DummyResp:
    def __init__(self, data):
        self._data = data

    def read(self):
        return json.dumps(self._data).encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


def test_render_prompt(monkeypatch):
    items = [{"id": "p1:1", "prompt_id": "p1", "version": "1", "template": "Hi {name}"}]
    table = FakeTable(items)
    monkeypatch.setattr(sys.modules["boto3"], "resource", lambda name: FakeResource(table), raising=False)
    monkeypatch.setenv("PROMPT_LIBRARY_TABLE", "tbl")
    monkeypatch.setenv("ROUTER_ENDPOINT", "http://router")

    sent = {}

    def fake_urlopen(req):
        sent["url"] = req.full_url
        sent["data"] = json.loads(req.data.decode())
        return DummyResp({"ok": True})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    module = load_lambda("engine", "services/prompt-engine/prompt-engine-lambda/app.py")
    out = module.lambda_handler({"prompt_id": "p1", "variables": {"name": "Bob"}}, {})
    assert sent["url"] == "http://router"
    assert sent["data"]["prompt"] == "Hi Bob"
    assert out["ok"] is True


def test_missing_variable(monkeypatch):
    items = [{"id": "p1:1", "prompt_id": "p1", "version": "1", "template": "Hi {name}"}]
    table = FakeTable(items)
    monkeypatch.setattr(sys.modules["boto3"], "resource", lambda name: FakeResource(table), raising=False)
    monkeypatch.setenv("PROMPT_LIBRARY_TABLE", "tbl")
    monkeypatch.setenv("ROUTER_ENDPOINT", "http://router")
    monkeypatch.setattr(urllib.request, "urlopen", lambda r: (_ for _ in ()).throw(AssertionError("should not call")))

    module = load_lambda("engine_missing", "services/prompt-engine/prompt-engine-lambda/app.py")
    with pytest.raises(ValueError):
        module.lambda_handler({"prompt_id": "p1"}, {})


def test_dynamo_failure(monkeypatch):
    class BadTable(FakeTable):
        def scan(self, *a, **k):
            raise RuntimeError("db boom")

    table = BadTable()
    monkeypatch.setattr(sys.modules["boto3"], "resource", lambda name: FakeResource(table), raising=False)
    monkeypatch.setenv("PROMPT_LIBRARY_TABLE", "tbl")
    monkeypatch.setenv("ROUTER_ENDPOINT", "http://router")
    module = load_lambda("engine_db", "services/prompt-engine/prompt-engine-lambda/app.py")
    out = module.lambda_handler({"prompt_id": "p1"}, {})
    assert "db boom" in out["error"]


def test_router_failure(monkeypatch):
    items = [{"id": "p1:1", "prompt_id": "p1", "version": "1", "template": "x"}]
    table = FakeTable(items)
    monkeypatch.setattr(sys.modules["boto3"], "resource", lambda name: FakeResource(table), raising=False)
    monkeypatch.setenv("PROMPT_LIBRARY_TABLE", "tbl")
    monkeypatch.setenv("ROUTER_ENDPOINT", "http://router")
    monkeypatch.setattr(urllib.request, "urlopen", lambda r: (_ for _ in ()).throw(RuntimeError("net")))

    module = load_lambda("engine_route", "services/prompt-engine/prompt-engine-lambda/app.py")
    out = module.lambda_handler({"prompt_id": "p1"}, {})
    assert "net" in out["error"]
