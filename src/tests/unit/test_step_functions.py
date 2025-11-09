"""
Unit tests for Step Functions state machine definition.
"""
import pytest
import json

from src.pipeline.step_functions import get_state_machine_definition, get_state_machine_definition_json


class TestStepFunctions:
    """Test Step Functions state machine definition."""
    
    def test_get_state_machine_definition(self):
        """Test state machine definition generation."""
        stage1_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-1-preview'
        stage2_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-2-intermediate'
        stage3_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-3-final'
        
        state_machine = get_state_machine_definition(stage1_arn, stage2_arn, stage3_arn)
        
        # Verify structure
        assert 'Comment' in state_machine
        assert 'StartAt' in state_machine
        assert 'States' in state_machine
        assert state_machine['StartAt'] == 'Stage1Preview'
        
        # Verify states
        states = state_machine['States']
        assert 'Stage1Preview' in states
        assert 'Stage2Intermediate' in states
        assert 'Stage3Final' in states
        assert 'PipelineFailed' in states
        
        # Verify Stage1Preview
        stage1 = states['Stage1Preview']
        assert stage1['Type'] == 'Task'
        assert stage1['Resource'] == stage1_arn
        assert stage1['Next'] == 'Stage2Intermediate'
        assert 'Retry' in stage1
        assert 'Catch' in stage1
        assert stage1['TimeoutSeconds'] == 300
        
        # Verify Stage2Intermediate
        stage2 = states['Stage2Intermediate']
        assert stage2['Type'] == 'Task'
        assert stage2['Resource'] == stage2_arn
        assert stage2['Next'] == 'Stage3Final'
        assert 'Retry' in stage2
        assert 'Catch' in stage2
        assert stage2['TimeoutSeconds'] == 300
        
        # Verify Stage3Final
        stage3 = states['Stage3Final']
        assert stage3['Type'] == 'Task'
        assert stage3['Resource'] == stage3_arn
        assert stage3['End'] is True
        assert 'Retry' in stage3
        assert 'Catch' in stage3
        assert stage3['TimeoutSeconds'] == 300
        
        # Verify PipelineFailed
        failed = states['PipelineFailed']
        assert failed['Type'] == 'Fail'
        assert 'Error' in failed
        assert 'Cause' in failed
    
    def test_get_state_machine_definition_json(self):
        """Test state machine definition as JSON string."""
        stage1_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-1-preview'
        stage2_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-2-intermediate'
        stage3_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-3-final'
        
        json_str = get_state_machine_definition_json(stage1_arn, stage2_arn, stage3_arn)
        
        # Verify it's valid JSON
        state_machine = json.loads(json_str)
        assert 'Comment' in state_machine
        assert 'StartAt' in state_machine
        assert 'States' in state_machine
    
    def test_retry_configuration(self):
        """Test retry configuration in state machine."""
        stage1_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-1-preview'
        stage2_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-2-intermediate'
        stage3_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-3-final'
        
        state_machine = get_state_machine_definition(stage1_arn, stage2_arn, stage3_arn)
        
        # Verify retry configuration for each stage
        stage1_retry = state_machine['States']['Stage1Preview']['Retry'][0]
        assert stage1_retry['IntervalSeconds'] == 1
        assert stage1_retry['MaxAttempts'] == 3
        assert stage1_retry['BackoffRate'] == 2.0
        
        stage2_retry = state_machine['States']['Stage2Intermediate']['Retry'][0]
        assert stage2_retry['IntervalSeconds'] == 2
        assert stage2_retry['MaxAttempts'] == 3
        assert stage2_retry['BackoffRate'] == 2.0
        
        stage3_retry = state_machine['States']['Stage3Final']['Retry'][0]
        assert stage3_retry['IntervalSeconds'] == 4
        assert stage3_retry['MaxAttempts'] == 3
        assert stage3_retry['BackoffRate'] == 2.0
    
    def test_error_handling(self):
        """Test error handling configuration."""
        stage1_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-1-preview'
        stage2_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-2-intermediate'
        stage3_arn = 'arn:aws:lambda:us-east-1:123456789012:function:stage-3-final'
        
        state_machine = get_state_machine_definition(stage1_arn, stage2_arn, stage3_arn)
        
        # Verify error catch blocks
        stage1_catch = state_machine['States']['Stage1Preview']['Catch'][0]
        assert stage1_catch['ErrorEquals'] == ['States.ALL']
        assert stage1_catch['Next'] == 'PipelineFailed'
        assert stage1_catch['ResultPath'] == '$.error'
        
        # Verify PipelineFailed state
        failed = state_machine['States']['PipelineFailed']
        assert failed['Type'] == 'Fail'
        assert failed['Error'] == 'PipelineExecutionFailed'

