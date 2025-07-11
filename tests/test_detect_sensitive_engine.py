import importlib.util
import sys
import types


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stub_presidio(monkeypatch, calls):
    provider_mod = types.SimpleNamespace()

    class FakeProvider:
        def __init__(self, nlp_configuration):
            calls['conf'] = nlp_configuration

        def create_engine(self):
            calls['created'] = True
            return 'nlp'

    provider_mod.NlpEngineProvider = FakeProvider

    analyzer_mod = types.SimpleNamespace(
        AnalyzerEngine=lambda nlp_engine=None, supported_languages=None: {
            'engine': nlp_engine,
            'langs': supported_languages,
        }
    )
    monkeypatch.setitem(sys.modules, 'presidio_analyzer', analyzer_mod)
    monkeypatch.setitem(sys.modules, 'presidio_analyzer.nlp_engine', provider_mod)


def test_build_engine_spacy(monkeypatch):
    module = load_lambda('detect_spacy', 'services/anonymization/src/detect_sensitive_info_lambda.py')
    calls = {}
    _stub_presidio(monkeypatch, calls)
    monkeypatch.setenv('NER_LIBRARY', 'spacy')
    monkeypatch.setenv('SPACY_MODEL', 'custom-model')
    engine = module._build_engine('SPACY_MODEL', 'HF_MODEL')
    assert calls['conf']['nlp_engine_name'] == 'spacy'
    assert calls['conf']['models'][0]['model_name'] == 'custom-model'
    assert engine['langs'] == [module.LANGUAGE]


def test_build_engine_hf(monkeypatch):
    module = load_lambda('detect_hf', 'services/anonymization/src/detect_sensitive_info_lambda.py')
    calls = {}
    _stub_presidio(monkeypatch, calls)
    monkeypatch.setenv('NER_LIBRARY', 'hf')
    monkeypatch.setenv('HF_MODEL', 'bert-base')
    engine = module._build_engine('SPACY_MODEL', 'HF_MODEL')
    assert calls['conf']['nlp_engine_name'] == 'transformers'
    assert calls['conf']['models'][0]['model_name'] == 'bert-base'
    assert engine['engine'] == 'nlp'


