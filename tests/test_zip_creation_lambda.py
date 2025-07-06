import importlib.util
import types
import sys
import xml.etree.ElementTree as builtin_ET


def _stub_botocore(monkeypatch):
    botocore = types.ModuleType("botocore")
    exc_mod = types.ModuleType("botocore.exceptions")

    class ClientError(Exception):
        pass

    exc_mod.ClientError = ClientError
    botocore.exceptions = exc_mod
    monkeypatch.setitem(sys.modules, "botocore", botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", exc_mod)


def _stub_defusedxml(monkeypatch):
    defusedxml = types.ModuleType("defusedxml")
    defusedxml.ElementTree = builtin_ET
    monkeypatch.setitem(sys.modules, "defusedxml", defusedxml)
    monkeypatch.setitem(sys.modules, "defusedxml.ElementTree", builtin_ET)


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_multiple_tags_basic(monkeypatch):
    _stub_botocore(monkeypatch)
    _stub_defusedxml(monkeypatch)
    module = load_lambda('zip_creation', 'temp-services/zip-processing/zip-creation-lambda/app.py')
    xml = '<root><PolNumber>123</PolNumber><TrackingID>T-1</TrackingID></root>'
    out = module.parse_multiple_tags(xml, ['PolNumber', 'TrackingID'])
    assert out == {'PolNumber': '123', 'TrackingID': 'T-1'}


def test_parse_multiple_tags_missing(monkeypatch):
    _stub_botocore(monkeypatch)
    _stub_defusedxml(monkeypatch)
    module = load_lambda('zip_creation_missing', 'temp-services/zip-processing/zip-creation-lambda/app.py')
    xml = '<root><PolNumber>123</PolNumber></root>'
    out = module.parse_multiple_tags(xml, ['PolNumber', 'TrackingID'])
    assert out == {'PolNumber': '123', 'TrackingID': None}
