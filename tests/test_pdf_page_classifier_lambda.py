import importlib.util


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_event(prefix):
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": f"{prefix}doc1/page_001.pdf"},
                }
            }
        ]
    }

def test_pdf_page_classifier_default(monkeypatch, s3_stub, config):
    prefix = '/parameters/aio/ameritasAI/dev'
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    config[f'{prefix}/BUCKET_NAME'] = 'bucket'
    pdf_page_prefix = 'pdf-pages/'
    pdf_text_prefix = 'text-pages/'
    pdf_scan_prefix = 'scan-pages/'
    config[f'{prefix}/PDF_PAGE_PREFIX'] = pdf_page_prefix
    config[f'{prefix}/PDF_TEXT_PAGE_PREFIX'] = pdf_text_prefix
    config[f'{prefix}/PDF_SCAN_PAGE_PREFIX'] = pdf_scan_prefix
    module = load_lambda('classifier', 'services/idp/src/pdf_page_classifier_lambda.py')

    s3_stub.objects[('bucket', f'{pdf_page_prefix}doc1/page_001.pdf')] = b'data'
    monkeypatch.setattr(module, '_page_has_text', lambda b: True)

    event = _make_event(pdf_page_prefix)
    module.lambda_handler(event, {})

    assert ('bucket', f'{pdf_text_prefix}doc1/page_001.pdf') in s3_stub.objects

def test_pdf_page_classifier_force(monkeypatch, s3_stub, config):
    prefix = '/parameters/aio/ameritasAI/dev'
    config['/parameters/aio/ameritasAI/SERVER_ENV'] = 'dev'
    config[f'{prefix}/BUCKET_NAME'] = 'bucket'
    pdf_page_prefix = 'pdf-pages/'
    pdf_text_prefix = 'text-pages/'
    pdf_scan_prefix = 'scan-pages/'
    config[f'{prefix}/PDF_PAGE_PREFIX'] = pdf_page_prefix
    config[f'{prefix}/PDF_TEXT_PAGE_PREFIX'] = pdf_text_prefix
    config[f'{prefix}/PDF_SCAN_PAGE_PREFIX'] = pdf_scan_prefix
    config[f'{prefix}/FORCE_OCR'] = 'true'
    module = load_lambda('classifier_force', 'services/idp/src/pdf_page_classifier_lambda.py')

    s3_stub.objects[('bucket', f'{pdf_page_prefix}doc1/page_001.pdf')] = b'data'
    monkeypatch.setattr(module, '_page_has_text', lambda b: True)

    event = _make_event(pdf_page_prefix)
    module.lambda_handler(event, {})

    assert ('bucket', f'{pdf_scan_prefix}doc1/page_001.pdf') in s3_stub.objects

