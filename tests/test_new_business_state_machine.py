
def test_new_business_state_machine_definition():
    with open('use-cases/new-business-intake/template.yaml') as fh:
        content = fh.read()

    assert 'StartAt: IngestFile' in content
    assert 'ExtractFields:' in content
    assert 'GenerateXML:' in content
    assert 'IntakeStateMachineArn' in content
