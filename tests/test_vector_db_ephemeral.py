import importlib.util
import os
import time
import sys


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTable:
    def __init__(self, items=None):
        self.items = items or []
        self.put_calls = []
        self.deleted = []

    def put_item(self, Item=None):
        self.put_calls.append(Item)

    def scan(self):
        return {"Items": list(self.items)}

    def delete_item(self, Key=None):
        self.deleted.append(Key)
        self.items = [i for i in self.items if i.get("collection_name") != Key.get("collection_name")]


class FakeResource:
    def __init__(self, table):
        self._table = table

    def Table(self, name):
        return self._table


class FakeMilvus:
    def __init__(self, collection_name=None, *a, **k):
        self.collection_name = collection_name or os.environ.get("MILVUS_COLLECTION", "docs")
        self.created = False
        self.dropped = False

    def create_collection(self, dimension=768):
        self.created = True

    def drop_collection(self):
        self.dropped = True


def test_create_ephemeral(monkeypatch):
    table = FakeTable()
    monkeypatch.setenv("EPHEMERAL_TABLE", "tbl")
    monkeypatch.setenv("MILVUS_COLLECTION", "docs")
    import boto3
    monkeypatch.setattr(sys.modules["boto3"], "resource", lambda name: FakeResource(table), raising=False)
    import common_utils.get_ssm as g
    monkeypatch.setattr(g, "get_config", lambda name, **_: None)
    import common_utils
    monkeypatch.setattr(common_utils, "MilvusClient", FakeMilvus)
    module = load_module("milvus", "services/vector-db/src/milvus_handler_lambda.py")
    event = {"operation": "create", "ephemeral": True, "expires_at": 100}
    out = module.lambda_handler(event, {})
    assert out["created"] is True
    assert table.put_calls == [{"collection_name": "docs", "expires_at": 100}]


def test_cleanup_removes_expired(monkeypatch):
    now = int(time.time())
    items = [
        {"collection_name": "c1", "expires_at": now - 10},
        {"collection_name": "c2", "expires_at": now + 100},
    ]
    table = FakeTable(items)
    import common_utils.get_ssm as g
    monkeypatch.setattr(g, "get_config", lambda name, **_: None)
    monkeypatch.setenv("EPHEMERAL_TABLE", "tbl")
    import boto3
    monkeypatch.setattr(sys.modules["boto3"], "resource", lambda name: FakeResource(table), raising=False)
    module = load_module("cleanup", "services/vector-db/src/jobs/cleanup_ephemeral_lambda.py")
    module.ddb = FakeResource(table)
    monkeypatch.setattr(module, "MilvusClient", FakeMilvus)
    result = module.lambda_handler({}, {})
    assert result["dropped"] == 1
    assert table.deleted == [{"collection_name": "c1"}]


def test_cleanup_drops_multiple(monkeypatch):
    now = int(time.time())
    items = [
        {"collection_name": "c1", "expires_at": now - 5},
        {"collection_name": "c2", "expires_at": now - 1},
        {"collection_name": "c3", "expires_at": now + 100},
    ]
    table = FakeTable(items)
    import common_utils.get_ssm as g
    monkeypatch.setattr(g, "get_config", lambda name, **_: None)
    monkeypatch.setenv("EPHEMERAL_TABLE", "tbl")
    import boto3
    monkeypatch.setattr(sys.modules["boto3"], "resource", lambda name: FakeResource(table), raising=False)
    module = load_module("cleanup", "services/vector-db/src/jobs/cleanup_ephemeral_lambda.py")
    module.ddb = FakeResource(table)

    dropped = []

    class RecordingMilvus(FakeMilvus):
        def drop_collection(self):
            super().drop_collection()
            dropped.append(self.collection_name)

    monkeypatch.setattr(module, "MilvusClient", RecordingMilvus)
    result = module.lambda_handler({}, {})
    assert result["dropped"] == 2
    assert set(dropped) == {"c1", "c2"}
    assert table.deleted == [{"collection_name": "c1"}, {"collection_name": "c2"}]
    remaining = [i["collection_name"] for i in table.items]
    assert remaining == ["c3"]


def test_cleanup_no_expired(monkeypatch):
    now = int(time.time())
    items = [{"collection_name": "c1", "expires_at": now + 100}]
    table = FakeTable(items)
    import common_utils.get_ssm as g
    monkeypatch.setattr(g, "get_config", lambda name, **_: None)
    monkeypatch.setenv("EPHEMERAL_TABLE", "tbl")
    import boto3
    monkeypatch.setattr(sys.modules["boto3"], "resource", lambda name: FakeResource(table), raising=False)
    module = load_module("cleanup", "services/vector-db/src/jobs/cleanup_ephemeral_lambda.py")
    module.ddb = FakeResource(table)

    dropped = []

    class RecordingMilvus(FakeMilvus):
        def drop_collection(self):
            super().drop_collection()
            dropped.append(self.collection_name)

    monkeypatch.setattr(module, "MilvusClient", RecordingMilvus)
    result = module.lambda_handler({}, {})
    assert result["dropped"] == 0
    assert dropped == []
    assert table.deleted == []
    remaining = [i["collection_name"] for i in table.items]
    assert remaining == ["c1"]
