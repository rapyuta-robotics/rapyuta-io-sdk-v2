# AI Agent Instructions

This file provides guidance to AI coding assistants (Claude Code, GitHub Copilot, etc.) when working with code in this repository.

## Commands

```bash
# Install dependencies (dev mode)
uv sync --all-extras --dev

# Run all tests with coverage
uv run pytest tests/ --cov

# Run a single test
uv run pytest tests/sync_tests/test_project.py::test_list_projects_success -v
uv run pytest tests/async_tests/test_project_async.py::test_list_projects_success -v

# Lint and format
uvx ruff==0.16.9 check --fix .
uvx ruff==0.16.9 format .
uvx ruff==0.16.9 check .
uvx ruff==0.16.9 format --check .

# Build
uv build
```

Ruff is strict: 88-character lines, complexity <= 5, and explicit limits on
arguments, branches, statements, local variables, and nesting. See
`pyproject.toml` and `CONTRIBUTING.md` for the complete policy. Refactor to satisfy
the rules; do not weaken the configuration or add blanket suppressions. Any
necessary rule-specific suppression needs an explanation. Run both lint and
format checks before completing a change, and report any remaining violations.

## Architecture

This is a Python SDK for the rapyuta.io platform v2 API (Python 3.13+, managed with `uv`).

### Client Layer

`rapyuta_io_sdk_v2/client.py` and `async_client.py` are the primary entry points — thin wrappers around `httpx` (sync/async respectively) exposing CRUD methods for all platform resources. Both are ~2600 lines and mirror each other closely. Organization and project context is passed as HTTP headers (`organization_guid`, `project_guid`).

### Models

`rapyuta_io_sdk_v2/models/` — Pydantic models following Kubernetes conventions with `kind`, `metadata`, `spec`, `status` fields. Key base classes:

- `BaseObject` — adds `apiVersion`
- `BaseMetadata` — adds `name`, `guid`, `labels`, timestamps, creator, organization/project refs
- `BaseList[T]` — generic paginated list with `metadata.continue_` cursor token

Resource models inherit from these bases. Field aliases handle snake_case Python ↔ camelCase API translation.

### Configuration

`rapyuta_io_sdk_v2/config.py` — `Configuration` dataclass managing host selection per environment. Environments: `ga` (production), `qa`, `dev`, `local`, `pr-*`. Bearer token auth is set via `auth_token`.

### Utilities & Error Handling

- `exceptions.py` — HTTP status code → custom exception mapping (`UnauthorizedAccessError`, `HttpNotFoundError`, `InternalServerError`, etc.)
- `utils.py` — `walk_pages()` for transparent cursor-based pagination
- `pydantic_source.py` — Custom Pydantic settings source for loading config from the ConfigTree API

### Tests

Parallel structure: `tests/sync_tests/` and `tests/async_tests/` mirror each other. Fixtures (client instances, mock data) live in `tests/utils/fixtures.py`. Tests mock `httpx.Client.get/post/put/delete` directly; no real network calls.
