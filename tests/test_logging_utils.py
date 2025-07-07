import io
import json
import importlib
import logging

import pytest


def reload_module():
    import common_utils.logging_utils as lu
    return importlib.reload(lu)


def test_log_level_from_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    lu = reload_module()
    logger = lu.configure_logger("env-test")
    assert logger.level == logging.DEBUG


def test_log_level_from_ssm(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.setattr(
        "common_utils.get_ssm.get_config", lambda name: "warning" if name == "LOG_LEVEL" else None
    )
    lu = reload_module()
    logger = lu.configure_logger("ssm-level")
    assert logger.level == logging.WARNING


def _emit(logger):
    stream = io.StringIO()
    for h in logger.handlers:
        h.stream = stream
    logger.info("hi")
    return stream.getvalue().strip()


def test_json_logging_env(monkeypatch):
    monkeypatch.setenv("LOG_JSON", "true")
    lu = reload_module()
    logger = lu.configure_logger("json-env")
    out = _emit(logger)
    assert json.loads(out)["message"] == "hi"


def test_json_logging_ssm(monkeypatch):
    monkeypatch.delenv("LOG_JSON", raising=False)
    monkeypatch.setattr(
        "common_utils.get_ssm.get_config", lambda name: "true" if name == "LOG_JSON" else None
    )
    lu = reload_module()
    logger = lu.configure_logger("json-ssm")
    out = _emit(logger)
    assert json.loads(out)["message"] == "hi"
