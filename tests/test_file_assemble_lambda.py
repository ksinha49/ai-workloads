import importlib.util


def load_lambda(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_assemble_skips_merge(monkeypatch, s3_stub, config):
    module = load_lambda('assemble', 'services/file-assembly/file-assemble-lambda/app.py')

    s3_stub.objects[('bucket', 'extracted/test.docx')] = b'orig'
    s3_stub.objects[('bucket', 'summary/test.pdf')] = b'sum'

    monkeypatch.setattr(module, 'merge_pdfs', lambda *a, **k: (_ for _ in ()).throw(AssertionError('merge called')))

    uploaded = {}

    def fake_upload(data, name, bucket, s3_client=s3_stub):
        uploaded['data'] = data
        uploaded['name'] = name
        uploaded['bucket'] = bucket
        return {'summarized_file': f's3://{bucket}/{name}'}

    monkeypatch.setattr(module, 'upload_to_s3', fake_upload)

    event = {
        'organic_bucket': 'bucket',
        'organic_bucket_key': 'extracted/test.docx',
        'summary_bucket_name': 'bucket',
        'summary_bucket_key': 'summary/test.pdf',
    }
    out = module.assemble_files(event, {}, s3_stub)
    assert uploaded['data'] == b'sum'
    assert uploaded['name'] == 'merged/test.docx'
    assert out['summarized_file'] == 's3://bucket/merged/test.docx'
    assert out['merged'] is False


def test_assemble_merges(monkeypatch, s3_stub, config):
    module = load_lambda('assemble2', 'services/file-assembly/file-assemble-lambda/app.py')

    s3_stub.objects[('bucket', 'extracted/test.pdf')] = b'orig'
    s3_stub.objects[('bucket', 'summary/test.pdf')] = b'sum'

    called = {}
    def fake_merge(summary, organic):
        called['called'] = True
        return b'merged'
    monkeypatch.setattr(module, 'merge_pdfs', fake_merge)

    uploaded = {}
    def fake_upload(data, name, bucket, s3_client=s3_stub):
        uploaded['data'] = data
        uploaded['name'] = name
        uploaded['bucket'] = bucket
        return {'summarized_file': f's3://{bucket}/{name}'}

    monkeypatch.setattr(module, 'upload_to_s3', fake_upload)

    event = {
        'organic_bucket': 'bucket',
        'organic_bucket_key': 'extracted/test.pdf',
        'summary_bucket_name': 'bucket',
        'summary_bucket_key': 'summary/test.pdf',
    }
    out = module.assemble_files(event, {}, s3_stub)
    assert called.get('called')
    assert uploaded['data'] == b'merged'
    assert uploaded['name'] == 'merged/test.pdf'
    assert out['summarized_file'] == 's3://bucket/merged/test.pdf'
    assert out['merged'] is True
