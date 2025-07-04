import importlib.util
import sys
import json
import io


def test_predictive_routing_complex_short(monkeypatch):
    monkeypatch.setenv("CLASSIFIER_MODEL_ID", "clf")
    monkeypatch.setenv("WEAK_MODEL_ID", "weak")
    monkeypatch.setenv("STRONG_MODEL_ID", "strong")
    monkeypatch.setenv("LLM_INVOCATION_FUNCTION", "x")

    class DummyLambda:
        def invoke(self, **kwargs):
            return {"Payload": io.BytesIO(json.dumps({"reply": "ok"}).encode())}

    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: DummyLambda())

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    predictive_router = load("predictive_router_test", "common/layers/router-layer/python/predictive_router.py")
    monkeypatch.setitem(sys.modules, "predictive_router", predictive_router)

    heuristic_router = load("heuristic_router_test", "common/layers/router-layer/python/heuristic_router.py")
    monkeypatch.setitem(sys.modules, "heuristic_router", heuristic_router)

    cascading_router = load("cascading_router_test", "common/layers/router-layer/python/cascading_router.py")
    monkeypatch.setitem(sys.modules, "cascading_router", cascading_router)

    main_router = load("main_router_test", "common/layers/router-layer/python/main_router.py")
    monkeypatch.setitem(sys.modules, "main_router", main_router)

    monkeypatch.setattr(predictive_router, "invoke_classifier", lambda client, model, prompt: "complex")

    result = main_router.route_event({"prompt": "write a python function"})
    assert result["backend"] == "bedrock"
    assert result["model"] == "strong"
