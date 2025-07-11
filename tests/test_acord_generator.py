import importlib.util


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_acord_xml():
    module = load_lambda('acord', 'services/acord-generator/src/generate_xml_lambda.py')
    data = {
        'fields': {'PolNumber': 'PN123', 'InsuredName': 'Jane Doe'},
        'signatures': {'Insured': 'Jane Doe', 'DateSigned': '2024-01-01'},
    }
    xml = module.generate_acord_xml(data)
    assert '<PolNumber>PN123</PolNumber>' in xml
    assert '<InsuredName>Jane Doe</InsuredName>' in xml
    assert '<Insured>Jane Doe</Insured>' in xml
    assert '<DateSigned>2024-01-01</DateSigned>' in xml


def test_verify_signature_heuristic(monkeypatch):
    module = load_lambda('acord', 'services/acord-generator/src/generate_xml_lambda.py')

    class DummyImg:
        def convert(self, mode):
            return self
        def histogram(self):
            return [10]*50 + [0]*206
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(module, 'Image', type('I', (), {'open': lambda *a, **k: DummyImg()}))
    monkeypatch.setattr(module, 'SIGNATURE_MODEL_ENDPOINT', None, raising=False)
    monkeypatch.setattr(module, 'SIGNATURE_THRESHOLD', 0.05, raising=False)

    assert module.verify_signature(b'data') is True


def test_verify_signature_remote(monkeypatch):
    module = load_lambda('acord', 'services/acord-generator/src/generate_xml_lambda.py')

    def post(url, files=None):
        return type('R', (), {'json': lambda self=None: {'score': 0.9}, 'raise_for_status': lambda self: None})()

    monkeypatch.setattr(module, 'httpx', type('H', (), {'post': post}))
    monkeypatch.setattr(module, 'SIGNATURE_MODEL_ENDPOINT', 'http://model')
    monkeypatch.setattr(module, 'SIGNATURE_THRESHOLD', 0.8, raising=False)

    assert module.verify_signature(b'data') is True
