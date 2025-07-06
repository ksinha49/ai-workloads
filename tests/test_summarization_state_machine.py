from pathlib import Path

def test_summarization_template_contains_both_workflows():
    content = Path('services/summarization/template.yaml').read_text()
    assert 'SummarizationWorkflow:' in content
    assert 'FileProcessingStepFunction:' in content
    assert 'InvokeSummarizationWorkflow' in content
    assert 'SummarizationWorkflowArn' in content
    assert 'FileProcessingStepFunctionArn' in content
