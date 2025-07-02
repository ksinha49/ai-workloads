import importlib.util
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.file_ingestion.models import FileProcessingEvent


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_file_processing_lambda(monkeypatch, s3_stub, config):
    prefix = '/parameters/aio/ameritasAI/dev'
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    config[f'{prefix}/IDP_BUCKET'] = 'dest-bucket'
    config[f'{prefix}/RAW_PREFIX'] = 'raw/'

    s3_stub.objects[('bucket', 'path/test.docx')] = b'data'

    def copy_object(Bucket=None, Key=None, CopySource=None):
        src = (CopySource['Bucket'], CopySource['Key'])
        s3_stub.objects[(Bucket, Key)] = s3_stub.objects.get(src, b'')
        return {}

    setattr(s3_stub, 'copy_object', copy_object)

    module = load_lambda('file_proc', 'services/file-ingestion/file-processing-lambda/app.py')

    event = FileProcessingEvent(file='s3://bucket/path/test.docx', collection_name='c')
    resp = module.lambda_handler(event, {})
    assert resp['statusCode'] == 200
    body = resp['body']
    assert body['document_id'] == 'test'
    assert body['s3_location'] == 's3://dest-bucket/raw/test.docx'
    assert body['collection_name'] == 'c'
