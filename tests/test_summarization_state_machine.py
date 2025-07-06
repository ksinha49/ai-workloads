from pathlib import Path

def test_summarization_template_contains_workflow_only():
    content = Path('services/summarization/template.yaml').read_text()
    assert 'SummarizationWorkflow:' in content
    assert 'FileProcessingStepFunction' not in content
    assert 'SummarizationWorkflowArn' in content
