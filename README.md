# locatrix

Location Detection AI - Job Management API

## CI/CD Pipeline

This project uses GitHub Actions for automated builds, testing, and deployment.

### Workflow Triggers

The CI/CD pipeline is triggered by:
- **Push to main branch**: Triggers build, lint, test, and deployment to dev environment
- **Pull requests to main**: Triggers build, lint, and test (no deployment)
- **Tagged releases (v*)**: Triggers build, lint, test, and deployment to prod environment

### Pipeline Jobs

The pipeline consists of the following jobs:

1. **Build**: Builds the SAM application using `sam build`
2. **Lint**: Runs flake8 and mypy for code quality checks
3. **Test**: Runs unit, integration, and E2E tests using pytest
4. **Deploy Dev**: Deploys to dev environment on merge to main
5. **Deploy Prod**: Deploys to prod environment on tagged releases

### Required GitHub Secrets

The following secrets must be configured in GitHub repository settings:

- `AWS_ACCESS_KEY_ID`: AWS access key for deployment
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key for deployment

**Note**: These secrets should be configured with least privilege IAM permissions for deployment only.

### Environment Configuration

The project uses environment-specific SAM configuration files:

- `samconfig.toml`: Default configuration for local development
- `samconfig.dev.toml`: Dev environment configuration
- `samconfig.prod.toml`: Prod environment configuration

Each environment uses separate CloudFormation stacks:
- Dev: `location-detection-dev`
- Prod: `location-detection-prod`

### Deployment Procedures

#### Deploying to Dev Environment

Dev deployments happen automatically when code is merged to the main branch. The pipeline will:
1. Build the SAM application
2. Run linting and type checking
3. Run all tests (unit, integration, E2E)
4. Deploy to dev environment if all checks pass

#### Deploying to Prod Environment

Prod deployments happen automatically when a tag starting with `v` is pushed:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The pipeline will:
1. Build the SAM application
2. Run linting and type checking
3. Run all tests (unit, integration, E2E)
4. Deploy to prod environment if all checks pass
5. Create a GitHub release with deployment details

### Rollback Procedures

If a deployment fails or causes issues:

1. **CloudFormation Rollback**: SAM/CloudFormation automatically rolls back failed deployments
2. **Manual Rollback**: Use CloudFormation console or CLI to rollback to a previous stack version
3. **Code Rollback**: Revert the commit and push to trigger a new deployment

```bash
# Revert last commit
git revert HEAD
git push origin main

# Or rollback to a specific commit
git reset --hard <commit-hash>
git push --force origin main
```

**Warning**: Force pushing should be done with caution and team coordination.

### Status Reporting

The pipeline automatically reports status:
- **Pull Requests**: Status checks appear on PRs showing build, lint, and test results
- **Deployments**: Deployment status is logged in workflow runs
- **Releases**: Production deployments create GitHub releases with API URLs

### Local Development

For local development and testing:

```bash
# Build locally
sam build

# Run tests locally
pytest src/tests/unit/ -v
pytest src/tests/integration/ -v

# Deploy locally (requires AWS credentials)
sam deploy --config-env dev
```

### Troubleshooting

**Build Failures:**
- Check Python version (requires 3.11)
- Verify SAM CLI is installed correctly
- Check for dependency conflicts

**Test Failures:**
- Run tests locally to reproduce issues
- Check test logs in GitHub Actions workflow output
- Verify test data and mocks are configured correctly

**Deployment Failures:**
- Verify AWS credentials are configured correctly in GitHub Secrets
- Check IAM permissions for the deployment role
- Review CloudFormation stack events in AWS Console
- Verify SAM config files are correct for the environment

**Linting Failures:**
- Run `flake8 src/` locally to see issues
- Fix code style violations
- Update type hints if mypy reports errors

### Workflow File Location

The CI/CD workflow configuration is located at:
- `.github/workflows/ci-cd.yml`

### Additional Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Project Architecture](docs/architecture.md)
