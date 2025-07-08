
def test_aps_state_machine_definition():
    with open('use-cases/aps-summarization/template.yaml') as fh:
        content = fh.read()

    assert 'StartAt: CreateCollection' in content
    assert 'CreateCollection:' in content
    assert 'ProcessZip:' in content
    assert 'PostProcess:' in content
    assert 'ZipFileProcessingStepFunctionArn' in content
    assert 'VectorDbProxyFunctionArn' in content
