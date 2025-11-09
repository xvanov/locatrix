# Quick Start: Local Testing for Story 3.1

## Fastest Way to Test (Unit Tests)

```bash
# Run all new unit tests
pytest src/tests/unit/test_textract_service.py src/tests/unit/test_preview_service.py src/tests/unit/test_room_detection.py -v

# Run with coverage
pytest src/tests/unit/test_textract_service.py src/tests/unit/test_preview_service.py src/tests/unit/test_room_detection.py --cov=src/services/textract_service --cov=src/services/preview_service --cov=src/utils/room_detection --cov-report=term-missing
```

## Integration Tests

```bash
# Run preview pipeline integration tests
pytest src/tests/integration/test_preview_pipeline.py -v
```

## Full API Testing with SAM Local

**Terminal 1: Start API**
```bash
sam build
sam local start-api --port 3000
```

**Terminal 2: Run Playwright Tests**
```bash
npm run test:api
```

## Test Files Created

✅ `src/tests/unit/test_textract_service.py` - TextractService unit tests
✅ `src/tests/unit/test_preview_service.py` - PreviewService unit tests  
✅ `src/tests/unit/test_room_detection.py` - Room detection algorithm tests
✅ `src/tests/integration/test_preview_pipeline.py` - Preview pipeline integration tests

## Expected Test Results

- **Unit Tests**: ~15-20 tests covering all components
- **Integration Tests**: ~6 tests covering API endpoints
- **Playwright Tests**: 12 tests (already created in `tests/api/story-3-1-preview-pipeline.spec.ts`)

## Troubleshooting

**Import errors**: Run from project root directory
**Missing mocks**: All tests use `unittest.mock` - no AWS credentials needed
**SAM Local issues**: Ensure Docker Desktop is running

