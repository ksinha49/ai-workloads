import importlib.util
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'common', 'layers', 'common-utils', 'python'))
from models import FileProcessingEvent


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_file_processing_lambda(monkeypatch, s3_stub, config):
    prefix = '/parameters/aio/ameritasAI/dev'
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    config[f'{prefix}/IDP_BUCKET'] = 'dest-bucket'
    raw_prefix = 'raw/'
    config[f'{prefix}/RAW_PREFIX'] = raw_prefix

    s3_stub.objects[('bucket', 'path/test.docx')] = b'data'

    module = load_lambda('file_proc', 'services/file-ingestion/src/file_processing_lambda.py')

    event = FileProcessingEvent(file='s3://bucket/path/test.docx', collection_name='c')
    resp = module.lambda_handler(event, {})
    assert resp['statusCode'] == 200
    body = resp['body']
    assert len(body['document_id']) == 32 and all(c in '0123456789abcdef' for c in body['document_id'])
    assert body['s3_location'] == f's3://dest-bucket/{raw_prefix}test.docx'
    assert body['collection_name'] == 'c'
    # ensure the source file was tagged for deletion rather than removed
    assert ('bucket', 'path/test.docx') in s3_stub.objects
    assert s3_stub.tags[('bucket', 'path/test.docx')]['pending-delete'] == 'true'


def test_file_processing_lambda_copy_verification_failed(monkeypatch, s3_stub, config):
    prefix = '/parameters/aio/ameritasAI/dev'
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    config[f'{prefix}/IDP_BUCKET'] = 'dest-bucket'
    raw_prefix = 'raw/'
    config[f'{prefix}/RAW_PREFIX'] = raw_prefix

    s3_stub.objects[('bucket', 'path/test.docx')] = b'data'

    def bad_copy(Bucket=None, Key=None, CopySource=None):
        s3_stub.objects[(Bucket, Key)] = b'bad'
        return {}

    monkeypatch.setattr(s3_stub, 'copy_object', bad_copy)

    module = load_lambda('file_proc_fail', 'services/file-ingestion/src/file_processing_lambda.py')

    event = FileProcessingEvent(file='s3://bucket/path/test.docx', collection_name='c')
    resp = module.lambda_handler(event, {})
    assert resp['statusCode'] == 500
    # source should remain and not be tagged since verification failed
    assert ('bucket', 'path/test.docx') in s3_stub.objects
    assert ('bucket', 'path/test.docx') not in s3_stub.tags


def test_file_processing_lambda_invalid_path(monkeypatch, config):
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    module = load_lambda('file_proc_inv', 'services/file-ingestion/src/file_processing_lambda.py')
    event = FileProcessingEvent(file='foo', collection_name='c')
    resp = module.lambda_handler(event, {})
    assert resp['statusCode'] == 400


def test_file_processing_lambda_bad_collection(monkeypatch, config):
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    module = load_lambda('file_proc_col', 'services/file-ingestion/src/file_processing_lambda.py')
    event = FileProcessingEvent(file='s3://bucket/test.pdf', collection_name='@@@')
    resp = module.lambda_handler(event, {})
    assert resp['statusCode'] == 400


def test_file_processing_lambda_bad_uri_traversal(monkeypatch, config):
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    module = load_lambda('file_proc_trav', 'services/file-ingestion/src/file_processing_lambda.py')
    event = FileProcessingEvent(file='s3://bucket/../../secret.txt', collection_name='c')
    resp = module.lambda_handler(event, {})
    assert resp['statusCode'] == 400


def test_file_processing_lambda_bad_uri_double_slash(monkeypatch, config):
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    module = load_lambda('file_proc_dslash', 'services/file-ingestion/src/file_processing_lambda.py')
    event = FileProcessingEvent(file='s3://bucket/path//test.pdf', collection_name='c')
    resp = module.lambda_handler(event, {})
    assert resp['statusCode'] == 400


def test_file_processing_lambda_bad_bucket(monkeypatch, config):
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    module = load_lambda('file_proc_bucket', 'services/file-ingestion/src/file_processing_lambda.py')
    event = FileProcessingEvent(file='s3://Bad_Bucket/test.pdf', collection_name='c')
    resp = module.lambda_handler(event, {})
    assert resp['statusCode'] == 400
