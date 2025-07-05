import importlib.util
import sys
import types
import pytest


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def faker_stub(monkeypatch):
    class FakeGen:
        def __init__(self):
            self.count = 0
        def name(self):
            self.count += 1
            return f"name{self.count}"
        def company(self):
            return "company"
        def city(self):
            return "city"
        def address(self):
            return "addr"
        def phone_number(self):
            return "phone"
        def email(self):
            return "email"
        def word(self):
            return "word"
    fake = FakeGen()
    fake_mod = types.SimpleNamespace(Faker=lambda: fake)
    monkeypatch.setitem(sys.modules, "faker", fake_mod)
    return fake


@pytest.fixture
def load_app(monkeypatch, faker_stub):
    def _load():
        return load_lambda("anon_app", "services/anonymization/src/3_mask_text_lambda.py")
    return _load


def _event(text="Alice met Bob."):
    return {
        "text": text,
        "entities": [
            {"text": "Alice", "start": 0, "end": 5, "type": "PERSON"},
            {"text": "Bob", "start": 10, "end": 13, "type": "PERSON"},
        ],
    }


def test_mask_mode(monkeypatch, load_app, config):
    monkeypatch.setenv("ANON_MODE", "mask")
    module = load_app()
    out = module.lambda_handler(_event(), {})
    assert out == {"text": "***** met ***."}


def test_pseudonymization(monkeypatch, load_app, faker_stub, config):
    monkeypatch.setenv("ANON_MODE", "pseudo")
    module = load_app()
    out = module.lambda_handler(_event(), {})
    assert out["text"] == "name1 met name2."
    repl = out.get("replacements", [])
    assert [r["replacement"] for r in repl] == ["name1", "name2"]


def test_tokenization(monkeypatch, load_app, config):
    monkeypatch.setenv("ANON_MODE", "token")
    monkeypatch.setenv("TOKEN_API_URL", "http://token")

    calls = []
    class Resp:
        def __init__(self, tok):
            self.tok = tok
        def raise_for_status(self):
            pass
        def json(self):
            return {"token": self.tok}

    def fake_post(url, json=None, timeout=None):
        tok = f"tok-{len(calls)+1}"
        calls.append(json)
        return Resp(tok)

    monkeypatch.setattr(sys.modules["httpx"], "post", fake_post)

    module = load_app()
    out = module.lambda_handler(_event(), {})
    assert out["text"] == "tok-1 met tok-2."
    repl = out.get("replacements", [])
    assert [r["replacement"] for r in repl] == ["tok-1", "tok-2"]


def test_tokenization_timeout(monkeypatch, load_app, config):
    monkeypatch.setenv("ANON_MODE", "token")
    monkeypatch.setenv("TOKEN_API_URL", "http://token")

    module = load_app()

    def raise_timeout(url, json=None, timeout=None):
        raise module.HTTPError("timeout")

    monkeypatch.setattr(sys.modules["httpx"], "post", raise_timeout)
    out = module.lambda_handler(_event(), {})
    assert out["text"] == "[REMOVED] met [REMOVED]."
    repl = out.get("replacements", [])
    assert [r["replacement"] for r in repl] == ["[REMOVED]", "[REMOVED]"]
