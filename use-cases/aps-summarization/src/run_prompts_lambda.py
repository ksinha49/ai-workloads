import json
import os
import boto3

sfn = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ.get('SUMMARIZATION_STATE_MACHINE_ARN', '')
PROMPTS_FILE = os.environ.get('PROMPTS_FILE', os.path.join(os.path.dirname(__file__), '..', 'prompts', '900_questions.json'))


def lambda_handler(event, context):
    """Start the summarization state machine with provided prompts."""
    try:
        with open(PROMPTS_FILE, 'r') as fh:
            prompts = json.load(fh)
    except Exception:
        prompts = []
    payload = {
        'prompts': prompts,
    }
    if isinstance(event, dict):
        payload.update(event)
    resp = sfn.start_execution(stateMachineArn=STATE_MACHINE_ARN, input=json.dumps(payload))
    return {'executionArn': resp['executionArn']}
