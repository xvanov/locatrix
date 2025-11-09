"""
Step Functions state machine definition for multi-stage room detection pipeline.

This module provides the Step Functions state machine definition
for orchestrating the three-stage pipeline: preview → intermediate → final.
"""
from typing import Dict, Any


def get_state_machine_definition(
    stage1_preview_function_arn: str,
    stage2_intermediate_function_arn: str,
    stage3_final_function_arn: str
) -> Dict[str, Any]:
    """
    Get Step Functions state machine definition for room detection pipeline.
    
    Args:
        stage1_preview_function_arn: ARN of Stage 1 Preview Lambda function
        stage2_intermediate_function_arn: ARN of Stage 2 Intermediate Lambda function
        stage3_final_function_arn: ARN of Stage 3 Final Lambda function
        
    Returns:
        State machine definition dictionary
    """
    state_machine = {
        "Comment": "Multi-stage room detection pipeline",
        "StartAt": "Stage1Preview",
        "States": {
            "Stage1Preview": {
                "Type": "Task",
                "Resource": stage1_preview_function_arn,
                "Next": "Stage2Intermediate",
                "Retry": [
                    {
                        "ErrorEquals": [
                            "States.TaskFailed",
                            "States.Timeout",
                            "ServiceUnavailable",
                            "Throttling",
                            "ThrottlingException"
                        ],
                        "IntervalSeconds": 1,
                        "MaxAttempts": 3,
                        "BackoffRate": 2.0
                    }
                ],
                "Catch": [
                    {
                        "ErrorEquals": ["States.ALL"],
                        "Next": "PipelineFailed",
                        "ResultPath": "$.error"
                    }
                ],
                "TimeoutSeconds": 300,
                "ResultPath": "$.stage1_result"
            },
            "Stage2Intermediate": {
                "Type": "Task",
                "Resource": stage2_intermediate_function_arn,
                "Next": "Stage3Final",
                "Retry": [
                    {
                        "ErrorEquals": [
                            "States.TaskFailed",
                            "States.Timeout",
                            "ServiceUnavailable",
                            "Throttling",
                            "ThrottlingException"
                        ],
                        "IntervalSeconds": 2,
                        "MaxAttempts": 3,
                        "BackoffRate": 2.0
                    }
                ],
                "Catch": [
                    {
                        "ErrorEquals": ["States.ALL"],
                        "Next": "PipelineFailed",
                        "ResultPath": "$.error"
                    }
                ],
                "TimeoutSeconds": 300,
                "ResultPath": "$.stage2_result"
            },
            "Stage3Final": {
                "Type": "Task",
                "Resource": stage3_final_function_arn,
                "End": True,
                "Retry": [
                    {
                        "ErrorEquals": [
                            "States.TaskFailed",
                            "States.Timeout",
                            "ServiceUnavailable",
                            "Throttling",
                            "ThrottlingException"
                        ],
                        "IntervalSeconds": 4,
                        "MaxAttempts": 3,
                        "BackoffRate": 2.0
                    }
                ],
                "Catch": [
                    {
                        "ErrorEquals": ["States.ALL"],
                        "Next": "PipelineFailed",
                        "ResultPath": "$.error"
                    }
                ],
                "TimeoutSeconds": 300,
                "ResultPath": "$.stage3_result"
            },
            "PipelineFailed": {
                "Type": "Fail",
                "Error": "PipelineExecutionFailed",
                "Cause": "One or more pipeline stages failed"
            }
        }
    }
    
    return state_machine


def get_state_machine_definition_json(
    stage1_preview_function_arn: str,
    stage2_intermediate_function_arn: str,
    stage3_final_function_arn: str
) -> str:
    """
    Get Step Functions state machine definition as JSON string.
    
    Args:
        stage1_preview_function_arn: ARN of Stage 1 Preview Lambda function
        stage2_intermediate_function_arn: ARN of Stage 2 Intermediate Lambda function
        stage3_final_function_arn: ARN of Stage 3 Final Lambda function
        
    Returns:
        State machine definition as JSON string
    """
    import json
    state_machine = get_state_machine_definition(
        stage1_preview_function_arn,
        stage2_intermediate_function_arn,
        stage3_final_function_arn
    )
    return json.dumps(state_machine, indent=2)

