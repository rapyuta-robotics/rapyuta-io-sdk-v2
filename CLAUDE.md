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
uvx ruff check --fix
uvx ruff format

# Build
uv build
```

## Architecture

This is a Python SDK for the rapyuta.io platform v2 API (Python 3.13+, managed with `uv`).

### Client Layer

`rapyuta_io_sdk_v2/client.py` and `async_client.py` are the primary entry points — thin wrappers around `httpx` (sync/async respectively) exposing CRUD methods for all platform resources. Both are ~2600 lines and mirror each other closely. Organization and project context is passed as HTTP headers (`organization_guid`, `project_guid`).

### Models

`rapyuta_io_sdk_v2/models/` — Pydantic models following Kubernetes conventions with `kind`, `metadata`, `spec`, `status` fields. Key base classes:

- `SDKModel` — accepts snake_case Python fields and explicit API aliases
- `BaseObject` — adds `api_version` (wire alias `apiVersion`)
- `BaseMetadata` — adds `name`, `guid`, `labels`, timestamps, creator, organization/project refs
- `BaseList[T]` — generic paginated list with `metadata.continue_` cursor token

Resource models inherit from these bases. Field aliases handle snake_case Python ↔ camelCase API translation.

### Configuration

`rapyuta_io_sdk_v2/config.py` — `Configuration(BaseSettings)` resolves constructor values, `RIO_` environment variables, and rio-cli JSON. `resolved_v2_api_host` and `resolved_rip_host` derive URLs from environment and overrides. `RequestContext` sets per-request scope and headers.

### Utilities & Error Handling

- `exceptions.py` — HTTP status code → custom exception mapping (`UnauthorizedAccessError`, `HttpNotFoundError`, `InternalServerError`, etc.)
- `pagination.py` — `Paginator`/`AsyncPaginator` collect all items or stream typed items/pages
- `pydantic_source/` — optional, lazy ConfigTree settings source
- `features.py` — validated runtime flags for ConfigTree source, Apply, and Charts; dependencies are package extras
- `apply/` — typed resource handlers, rendering, dependency planning, sync/async execution and structured reports
- `charts/` — chart repositories, bounded downloads, safe archives and Apply integration

### Tests

Parallel structure: `tests/sync_tests/` and `tests/async_tests/` mirror each other. Fixtures (client instances, mock data) live in `tests/utils/fixtures.py`. Tests mock `httpx.Client.get/post/put/delete` directly; no real network calls.
