# Test Fixtures Directory

This directory contains test assets and fixtures used by the test suite.

## Structure

- `blueprints/` - Sample blueprint images for testing
  - Store real blueprint images here (PNG, JPG, PDF formats)
  - Use descriptive names like `sample-floor-plan.jpg`, `test-blueprint.pdf`
  - These files are used by integration and E2E tests

## Usage

### In Playwright Tests

```typescript
import { readFileSync } from 'fs';
import { join } from 'path';

const blueprintPath = join(__dirname, '../fixtures/blueprints/sample-floor-plan.jpg');
const blueprintData = readFileSync(blueprintPath);
const blueprintBase64 = blueprintData.toString('base64');
```

### In Python Tests

```python
import base64
import os

blueprint_path = os.path.join(
    os.path.dirname(__file__),
    '..', 'fixtures', 'blueprints', 'sample-floor-plan.jpg'
)
with open(blueprint_path, 'rb') as f:
    blueprint_base64 = base64.b64encode(f.read()).decode('utf-8')
```

## Adding New Test Blueprints

1. Save your blueprint image to `tests/fixtures/blueprints/`
2. Use descriptive filenames (e.g., `sample-floor-plan.jpg`)
3. Keep file sizes reasonable (< 5MB for fast tests)
4. Document the source/type in a README if needed


