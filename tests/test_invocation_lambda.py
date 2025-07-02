import importlib.util
import json
import io
import sys
import types
import pytest


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_invoke_ollama(monkeypatch):
    sys.modules['httpx'].HTTPStatusError = type('E', (Exception,), {})
    monkeypatch.setenv('OLLAMA_ENDPOINT', 'http://ollama')
    monkeypatch.setenv('OLLAMA_DEFAULT_MODEL', 'phi')
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload
        def json(self):
            return self._payload
        def raise_for_status(self):
            pass

    import llm_invocation.backends as backends
    monkeypatch.setattr(backends.httpx, 'post', lambda url, json=None: FakeResponse({'reply': 'ok', 'model': json.get('model')}))
    out = module.lambda_handler({'backend': 'ollama', 'prompt': 'hi'}, {})
    assert out['reply'] == 'ok'
    assert out['model'] == 'phi'


def test_invoke_bedrock_runtime(monkeypatch):
    sys.modules['httpx'].HTTPStatusError = type('E', (Exception,), {})
    monkeypatch.delenv('BEDROCK_OPENAI_ENDPOINTS', raising=False)
    monkeypatch.delenv('BEDROCK_OPENAI_ENDPOINT', raising=False)
    monkeypatch.setenv('BEDROCK_TEMPERATURE', '0.2')
    monkeypatch.setenv('BEDROCK_NUM_CTX', '128')
    monkeypatch.setenv('BEDROCK_MAX_TOKENS', '99')
    monkeypatch.setenv('BEDROCK_TOP_P', '0.7')
    monkeypatch.setenv('BEDROCK_TOP_K', '7')
    monkeypatch.setenv('BEDROCK_MAX_TOKENS_TO_SAMPLE', '33')
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    class FakeRuntime:
        def invoke_model(self, body=None, modelId=None, contentType=None, accept=None):
            payload = json.loads(body)
            assert payload['temperature'] == 0.2
            assert payload['num_ctx'] == 128
            assert payload['max_tokens'] == 99
            assert payload['top_p'] == 0.7
            assert payload['top_k'] == 7
            assert payload['max_tokens_to_sample'] == 33
            data = {
                'choices': [
                    {'message': {'content': 'resp'}}
                ]
            }
            return {'body': io.BytesIO(json.dumps(data).encode())}

    import llm_invocation.backends as backends
    monkeypatch.setattr(backends.boto3, 'client', lambda name: FakeRuntime())
    out = module.lambda_handler({'backend': 'bedrock', 'prompt': 'hi', 'model': 'm'}, {})
    assert out['reply'] == 'resp'


def test_round_robin_ollama(monkeypatch):
    sys.modules['httpx'].HTTPStatusError = type('E', (Exception,), {})
    monkeypatch.setenv('OLLAMA_ENDPOINTS', 'http://o1,http://o2')
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    calls = []

    class FakeResponse:
        def __init__(self, url):
            self.url = url
        def json(self):
            return {'endpoint': self.url}
        def raise_for_status(self):
            pass

    def fake_post(url, json=None):
        calls.append(url)
        return FakeResponse(url)

    import llm_invocation.backends as backends
    monkeypatch.setattr(backends.httpx, 'post', fake_post)
    module.lambda_handler({'backend': 'ollama', 'prompt': 'hi'}, {})
    module.lambda_handler({'backend': 'ollama', 'prompt': 'hi'}, {})
    assert calls[0] != calls[1]


def test_round_robin_bedrock_openai(monkeypatch):
    sys.modules['httpx'].HTTPStatusError = type('E', (Exception,), {})
    monkeypatch.setenv('BEDROCK_OPENAI_ENDPOINTS', 'http://b1,http://b2')
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    calls = []

    class FakeResponse:
        def __init__(self, url):
            self.url = url
        def json(self):
            return {'endpoint': self.url}
        def raise_for_status(self):
            pass

    def fake_post(url, json=None, headers=None):
        calls.append(url)
        return FakeResponse(url)

    import llm_invocation.backends as backends2
    monkeypatch.setattr(backends2.httpx, 'post', fake_post)
    module.lambda_handler({'backend': 'bedrock', 'prompt': 'hi'}, {})
    module.lambda_handler({'backend': 'bedrock', 'prompt': 'hi'}, {})
    assert calls[0] != calls[1]


def test_bedrock_openai_defaults(monkeypatch):
    sys.modules['httpx'].HTTPStatusError = type('E', (Exception,), {})
    monkeypatch.setenv('BEDROCK_OPENAI_ENDPOINTS', 'http://b1')
    monkeypatch.setenv('BEDROCK_TEMPERATURE', '0.3')
    monkeypatch.setenv('BEDROCK_NUM_CTX', '200')
    monkeypatch.setenv('BEDROCK_MAX_TOKENS', '150')
    monkeypatch.setenv('BEDROCK_TOP_P', '0.8')
    monkeypatch.setenv('BEDROCK_TOP_K', '42')
    monkeypatch.setenv('BEDROCK_MAX_TOKENS_TO_SAMPLE', '123')
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    captured = {}

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
        def json(self):
            return {'ok': True}
        def raise_for_status(self):
            pass

    def fake_post(url, json=None, headers=None):
        captured['json'] = json
        return FakeResponse(json)

    import llm_invocation.backends as backends2
    monkeypatch.setattr(backends2.httpx, 'post', fake_post)
    module.lambda_handler({'backend': 'bedrock', 'prompt': 'hi'}, {})
    sent = captured['json']
    assert sent['temperature'] == 0.3
    assert sent['num_ctx'] == 200
    assert sent['max_tokens'] == 150
    assert sent['top_p'] == 0.8
    assert sent['top_k'] == 42
    assert sent['max_tokens_to_sample'] == 123


def test_ollama_defaults(monkeypatch):
    sys.modules['httpx'].HTTPStatusError = type('E', (Exception,), {})
    monkeypatch.setenv('OLLAMA_ENDPOINTS', 'http://o1')
    monkeypatch.setenv('OLLAMA_DEFAULT_MODEL', 'phi')
    monkeypatch.setenv('OLLAMA_NUM_CTX', '99')
    monkeypatch.setenv('OLLAMA_REPEAT_LAST_N', '7')
    monkeypatch.setenv('OLLAMA_REPEAT_PENALTY', '1.2')
    monkeypatch.setenv('OLLAMA_TEMPERATURE', '0.3')
    monkeypatch.setenv('OLLAMA_SEED', '5')
    monkeypatch.setenv('OLLAMA_STOP', 'END')
    monkeypatch.setenv('OLLAMA_NUM_PREDICT', '12')
    monkeypatch.setenv('OLLAMA_TOP_K', '23')
    monkeypatch.setenv('OLLAMA_TOP_P', '0.8')
    monkeypatch.setenv('OLLAMA_MIN_P', '0.02')
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    captured = {}

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
        def json(self):
            return {'ok': True}
        def raise_for_status(self):
            pass

    def fake_post(url, json=None):
        captured['json'] = json
        return FakeResponse(json)

    import llm_invocation.backends as backends2
    monkeypatch.setattr(backends2.httpx, 'post', fake_post)
    module.lambda_handler({'backend': 'ollama', 'prompt': 'hi'}, {})
    sent = captured['json']
    assert sent['model'] == 'phi'
    assert sent['num_ctx'] == 99
    assert sent['repeat_last_n'] == 7
    assert sent['repeat_penalty'] == 1.2
    assert sent['temperature'] == 0.3
    assert sent['seed'] == 5
    assert sent['stop'] == 'END'
    assert sent['num_predict'] == 12
    assert sent['top_k'] == 23
    assert sent['top_p'] == 0.8
    assert sent['min_p'] == 0.02


def test__invoke_bedrock_openai(monkeypatch):
    sys.modules['httpx'].HTTPStatusError = type('E', (Exception,), {})
    monkeypatch.setenv('BEDROCK_OPENAI_ENDPOINTS', 'http://b1')
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    class FakeResponse:
        def json(self):
            return {'foo': 'bar'}

        def raise_for_status(self):
            pass

    import llm_invocation.backends as backends
    monkeypatch.setattr(backends.httpx, 'post', lambda url, json=None, headers=None: FakeResponse())

    out = module.lambda_handler({'backend': 'bedrock', 'prompt': 'hi'}, {})
    assert out == {'foo': 'bar'}


def test_bedrock_openai_messages(monkeypatch):
    sys.modules['httpx'].HTTPStatusError = type('E', (Exception,), {})
    monkeypatch.setenv('BEDROCK_OPENAI_ENDPOINTS', 'http://b1')
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    captured = {}

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return {'ok': True}

        def raise_for_status(self):
            pass

    def fake_post(url, json=None, headers=None):
        captured['json'] = json
        return FakeResponse(json)

    import llm_invocation.backends as backends
    monkeypatch.setattr(backends.httpx, 'post', fake_post)

    module.lambda_handler({'backend': 'bedrock', 'prompt': 'hi', 'system_prompt': 'sys'}, {})
    messages = captured['json']['messages']
    assert messages == [{'role': 'system', 'content': 'sys'}, {'role': 'user', 'content': 'hi'}]
    assert 'prompt' not in captured['json']


def test_invoke_bedrock_runtime_with_system(monkeypatch):
    sys.modules['httpx'].HTTPStatusError = type('E', (Exception,), {})
    monkeypatch.delenv('BEDROCK_OPENAI_ENDPOINTS', raising=False)
    monkeypatch.delenv('BEDROCK_OPENAI_ENDPOINT', raising=False)
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    captured = {}

    class FakeRuntime:
        def invoke_model(self, body=None, modelId=None, contentType=None, accept=None):
            captured['body'] = json.loads(body)
            data = {'choices': [{'message': {'content': 'ok'}}]}
            return {'body': io.BytesIO(json.dumps(data).encode())}

    import llm_invocation.backends as backends
    monkeypatch.setattr(backends.boto3, 'client', lambda name: FakeRuntime())

    module.lambda_handler({'backend': 'bedrock', 'prompt': 'u', 'system_prompt': 's'}, {})
    assert captured['body']['messages'] == [
        {'role': 'system', 'content': 's'},
        {'role': 'user', 'content': 'u'},
    ]


def test_ollama_system_prompt(monkeypatch):
    sys.modules['httpx'].HTTPStatusError = type('E', (Exception,), {})
    monkeypatch.setenv('OLLAMA_ENDPOINT', 'http://o')
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    captured = {}

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return {'ok': True}

        def raise_for_status(self):
            pass

    def fake_post(url, json=None):
        captured['json'] = json
        return FakeResponse(json)

    import llm_invocation.backends as backends
    monkeypatch.setattr(backends.httpx, 'post', fake_post)

    module.lambda_handler({'backend': 'ollama', 'prompt': 'hi', 'system_prompt': 'sys'}, {})
    assert captured['json']['system'] == 'sys'


def test_make_selector_round_robin():
    from llm_invocation.backends import _make_selector

    select = _make_selector(['a', 'b', 'c'])
    assert [select() for _ in range(4)] == ['a', 'b', 'c', 'a']


def test_make_selector_empty():
    from llm_invocation.backends import _make_selector

    select = _make_selector([])
    with pytest.raises(RuntimeError):
        select()


def test_failed_endpoint_skipped(monkeypatch):
    class E(Exception):
        def __init__(self):
            self.response = types.SimpleNamespace(status_code=500, text='err')

    sys.modules['httpx'].HTTPStatusError = E
    monkeypatch.setenv('OLLAMA_ENDPOINTS', 'http://o1,http://o2')
    import importlib, llm_invocation.backends
    importlib.reload(llm_invocation.backends)
    module = load_lambda('invoke', 'services/llm-invocation/invoke-lambda/app.py')

    calls = []

    class FakeResponse:
        def __init__(self, url):
            self.url = url

        def json(self):
            return {'endpoint': self.url}

        def raise_for_status(self):
            pass

    def fake_post(url, json=None):
        calls.append(url)
        if len(calls) == 1:
            raise sys.modules['httpx'].HTTPStatusError()
        return FakeResponse(url)

    import llm_invocation.backends as backends_mod
    monkeypatch.setattr(backends_mod.httpx, 'post', fake_post)

    with pytest.raises(backends_mod.httpx.HTTPStatusError):
        module.lambda_handler({'backend': 'ollama', 'prompt': 'x'}, {})

    out = module.lambda_handler({'backend': 'ollama', 'prompt': 'x'}, {})
    assert out['endpoint'] == 'http://o2'
    assert calls == ['http://o1', 'http://o2']

