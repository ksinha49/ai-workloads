import importlib.util
import io
import types
import importlib.util
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'common', 'layers', 'common-utils', 'python'))

from models import DetectedEntity


def load_lambda(name):
    spec = importlib.util.spec_from_file_location(name, 'services/file-assembly/src/redact_file_lambda.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_map_boxes():
    module = load_lambda('redact')
    hocr = {"pages": [{"words": [
        {"text": "Hello", "bbox": [0, 0, 5, 5]},
        {"text": "World", "bbox": [6, 0, 10, 5]},
    ]}]}
    entities = [DetectedEntity(text='Hello', type='PERSON', start=0, end=5).__dict__]
    boxes = module._map_boxes(hocr, entities)
    assert boxes == {1: [[0, 0, 5, 5]]}


def test_redact_image(monkeypatch, s3_stub):
    module = load_lambda('redact_img')

    class DummyImage:
        def __init__(self):
            self.drawn = []
            self.format = 'PNG'

        def save(self, out, format=None):
            out.write(b'data')

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    class DummyDraw:
        def __init__(self, img):
            self.img = img
        def rectangle(self, bbox, fill=None):
            self.img.drawn.append(bbox)

    last = {}
    def open_stub(fh):
        img = DummyImage()
        last['img'] = img
        return img
    monkeypatch.setattr(module, 'Image', types.SimpleNamespace(open=open_stub))
    monkeypatch.setattr(module, 'ImageDraw', types.SimpleNamespace(Draw=DummyDraw))
    monkeypatch.setattr(module, 's3_client', s3_stub)

    img_bytes = b'img'
    s3_stub.objects[('bucket', 'file.png')] = img_bytes

    event = {
        'file': 's3://bucket/file.png',
        'hocr': {'pages': [{'words': [{'text': 'a', 'bbox': [0, 0, 1, 1]}]}]},
        'entities': [{'text': 'a', 'type': 'CHAR', 'start': 0, 'end': 1}],
    }
    resp = module.lambda_handler(event, {})
    assert resp['statusCode'] == 200
    assert ('bucket', 'redacted/file.png') in s3_stub.objects
    assert last['img'].drawn == [[0, 0, 1, 1]]
