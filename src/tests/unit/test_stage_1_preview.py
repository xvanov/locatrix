"""
Unit tests for Stage 1 preview pipeline Lambda handler.
"""
import json
from unittest.mock import patch, MagicMock, ANY

import pytest

from src.pipeline.stage_1_preview import lambda_handler
from src.models.job import Job, JobStatus
from src.utils.errors import ServiceUnavailableError


class _MockContext:
    """Simple mock Lambda context with request id."""

    def __init__(self, request_id: str = "req-test-123"):
        self.aws_request_id = request_id


@pytest.fixture(autouse=True)
def preview_env():
    """Ensure required environment variables are present for the handler."""
    with patch.dict(
        "os.environ",
        {
            "JOBS_TABLE_NAME": "test-jobs",
            "PREVIEW_CACHE_TABLE_NAME": "test-preview-cache",
            "BLUEPRINTS_BUCKET_NAME": "test-blueprints-bucket",
            "CACHE_BUCKET_NAME": "test-cache-bucket",
        },
        clear=False,
    ):
        yield


@patch("src.pipeline.stage_1_preview.detect_rooms")
@patch("src.pipeline.stage_1_preview.PreviewService")
@patch("src.pipeline.stage_1_preview.TextractService")
@patch("src.pipeline.stage_1_preview.JobService")
def test_lambda_handler_returns_error_when_cache_store_fails(
    mock_job_service,
    mock_textract_service,
    mock_preview_service,
    mock_detect_rooms,
):
    """The handler should surface an error when preview cache persistence fails."""
    job = Job(
        job_id="job_20250101_000001_abcd1234",
        status=JobStatus.PENDING,
        blueprint_s3_key="blueprints/job_20250101_000001_abcd1234/file.pdf",
        blueprint_format="pdf",
        blueprint_hash="hash123",
    )
    mock_job_service.return_value.get_job.return_value = job

    mock_textract_service.return_value.analyze_document.return_value = {
        "text_blocks": [],
        "layout_blocks": [],
        "metadata": {},
    }

    preview_instance = MagicMock()
    preview_instance.get_cached_preview.return_value = None
    preview_instance.store_textract_results.return_value = (
        "cache/textract/job_20250101_000001_abcd1234/analysis.json"
    )
    preview_instance.store_preview_cache.side_effect = ServiceUnavailableError(
        "DynamoDB", retry_after=5
    )
    mock_preview_service.return_value = preview_instance

    mock_detect_rooms.return_value = [
        {
            "id": "room_001",
            "bounding_box": [0, 0, 100, 100],
            "confidence": 0.9,
        }
    ]

    response = lambda_handler({"job_id": job.job_id}, _MockContext())

    assert response["statusCode"] == 503
    body = json.loads(response["body"])
    assert body["status"] == "error"
    assert body["error"]["code"] == "PREVIEW_CACHE_STORE_FAILED"
    assert body["error"]["details"]["job_id"] == job.job_id

    preview_instance.store_preview_cache.assert_called_once_with(
        job.blueprint_hash, ANY, "1.0.0"
    )

