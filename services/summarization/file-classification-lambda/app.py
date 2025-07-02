# ------------------------------------------------------------------------------
# app.py
# ------------------------------------------------------------------------------
"""
Module: app.py
Description:
  1. Retrieves SSM parameters using a proxy configuration.
  2. Starts an execution of a Step Function state machine.


Version: 1.0.2
Created: 2025-05-05
Last Modified: 2025-06-28
Modified By: Koushik Sinha
"""

from __future__ import annotations

import logging
from common_utils import configure_logger
import boto3
import json
from common_utils.get_ssm import (
    get_values_from_ssm,
    get_environment_prefix,
)

# Module Metadata
__author__ = "Koushik Sinha"  # Author name (please fill this in)
__version__ = "1.0.2"  # Version number of the module
__modified_by__ = "Koushik Sinha"


# ─── Logging Configuration ─────────────────────────────────────────────────────
logger = configure_logger(__name__)



# Create a new client for Step Functions
step_functions = boto3.client('stepfunctions')
ssm = boto3.client('ssm')



def lambda_handler(event: dict, context) -> dict:
    """Triggered by API upload events to start classification.

    1. Looks up the Step Function ARN from SSM and starts an execution with the
       provided event payload.
    2. Errors are logged and returned in the response.

    Returns a dictionary indicating success.
    """

    input_json = json.dumps(event)
    prefix = get_environment_prefix()
    state_machine_arn = get_values_from_ssm(f"{prefix}/STEP_FUNCTION_ARN")
    #state_machine_arn ="arn:aws:states:us-east-2:528757830986:stateMachine:zip-processing-sf"
    # Start the task execution using the Lambda function as a trigger
    try:
         response = step_functions.start_execution(
         stateMachineArn=state_machine_arn,
         input=input_json
         )

         logger.info(f"response: {response}")

         if 'error' in response:
           logger.error(response['error'])
    except Exception as e:
        logger.error(f"Error occurred while retrieving parameter: {e}")
    return {"status":"Success"}
