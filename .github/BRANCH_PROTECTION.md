# Branch Protection Rules

This document describes the required GitHub branch protection rules to prevent merging broken branches.

## Configuration for `main` Branch

To enforce these rules, configure the following on the `main` branch:

### Required Status Checks

The following status checks must pass before a PR can be merged:

1. **Unit tests (gate)** — `Unit tests (Python 3.11)`, `Unit tests (Python 3.12)`, `Unit tests (Python 3.13)`, `Unit tests (Python 3.14)`
2. **Integration tests** — Required to verify database and service interactions
3. **CLI acceptance tests** — Validates CLI code generation and commands
4. **Celery acceptance tests** — Ensures Celery worker functionality
5. **LLM/embedding acceptance tests** — Tests LLM integration
6. **Linting tests** — `Linting Tests (Python 3.11)`, `Linting Tests (Python 3.12)`, `Linting Tests (Python 3.13)`, `Linting Tests (Python 3.14)`
7. **All checks passed (merge gate)** — Aggregated status indicating all required checks have passed

### Setting Up Branch Protection via GitHub CLI

```bash
# Authenticate with GitHub (if not already authenticated)
gh auth login

# Configure branch protection for main branch
gh api repos/workfloworchestrator/orchestrator-core/branches/main/protection \
  -X PUT \
  -f required_status_checks='{"strict":true,"contexts":["Unit tests (Python 3.11)","Unit tests (Python 3.12)","Unit tests (Python 3.13)","Unit tests (Python 3.14)","Integration tests (Python 3.11 / Postgres 15 / Redis 7)","Integration tests (Python 3.14 / Postgres 17 / Redis 8)","CLI acceptance tests","Celery acceptance tests","LLM/embedding acceptance tests","Linting Tests (Python 3.11)","Linting Tests (Python 3.12)","Linting Tests (Python 3.13)","Linting Tests (Python 3.14)","All checks passed (merge gate)"]}' \
  -f enforce_admins=true \
  -f required_pull_request_reviews='{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1}' \
  -f allow_force_pushes=false \
  -f allow_deletions=false \
  -f require_linear_history=true
```

### Manual Configuration via GitHub Web UI

1. Go to your repository settings → **Branches**
2. Click **Add rule** under "Branch protection rules"
3. Enter `main` as the branch name pattern
4. Enable the following:
   - ✓ Require a pull request before merging
   - ✓ Require status checks to pass before merging
   - ✓ Require branches to be up to date before merging
   - ✓ Require strict status checks
   - ✓ Require code reviews before merging (1 approval)
   - ✓ Dismiss stale pull request approvals when new commits are pushed
   - ✓ Require signed commits
   - ✓ Allow force pushes: **No one**
   - ✓ Allow deletions: **False**
   - ✓ Require linear history

5. Select the following required status checks:
   - All Python version variants of unit tests
   - Integration tests
   - CLI acceptance tests
   - Celery acceptance tests
   - LLM acceptance tests
   - All Python version variants of linting tests
   - All checks passed (merge gate)

## Why These Rules Matter

- **Required Status Checks**: Prevent merging code that fails tests, breaking the main branch
- **Strict Status Checks**: Ensure the code is current with main before merging
- **Code Review**: At least one approval required before merge
- **Linear History**: Prevents merge commits, keeping history clean
- **No Force Push**: Prevents accidentally overwriting main branch history
- **No Deletions**: Protects against accidental branch deletion

## Monitoring

Check the `.github/workflows/run-tests.yml` file for the current set of required checks. The `all-checks-passed` job serves as the primary merge gate that aggregates all other status checks.
