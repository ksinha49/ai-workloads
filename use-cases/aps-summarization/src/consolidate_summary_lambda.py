import json
import boto3

sfn = boto3.client('stepfunctions')

def lambda_handler(event, context):
    """Collect outputs from a list of Step Function executions."""
    executions = event.get('executions', [])
    if isinstance(executions, str):
        executions = [executions]
    results = []
    for arn in executions:
        try:
            desc = sfn.describe_execution(executionArn=arn)
            output = desc.get('output')
            if output:
                try:
                    results.append(json.loads(output))
                except Exception:
                    results.append({'output': output})
        except Exception:
            results.append({'error': f'Failed to fetch {arn}'})
    return {'results': results}
