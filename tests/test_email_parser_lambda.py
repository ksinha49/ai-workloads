import importlib.util
from email.message import EmailMessage
import sys


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def test_email_parser(monkeypatch, s3_stub):
    monkeypatch.setenv("ATTACHMENTS_BUCKET", "att")

    monkeypatch.setattr(sys.modules["boto3"], "client", lambda name: s3_stub if name == "s3" else None)

    module = load_lambda(
        "parser", "services/email-parser-service/src/email_parser_lambda.py"
    )

    msg = EmailMessage()
    msg["From"] = "sender@example.com"
    msg["Subject"] = "Test"
    msg.set_content("Hello world")
    msg.add_attachment(b"data", maintype="text", subtype="plain", filename="a.txt")
    raw = msg.as_bytes()

    s3_stub.objects[("raw", "email.eml")] = raw


    module._s3 = s3_stub

    event = {"Records": [{"s3": {"bucket": {"name": "raw"}, "object": {"key": "email.eml"}}}]}
    module.lambda_handler(event, {})

    att_keys = [k for (b, k) in s3_stub.objects.keys() if b == "att"]
    assert len(att_keys) == 1
    assert s3_stub.objects[("att", att_keys[0])] == b"data"


