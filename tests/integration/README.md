# Integration Tests

These tests run against the app in-process via FastAPI TestClient and mock the
external user portal API using Prism.

The current suite is contract-first for TDD:

- Happy path proxy expectations for search/invite/list/delete routes
- Predictable failure expectations (no results, upstream 502, invalid payload)

When endpoint implementation is incomplete, these tests are expected to fail and
serve as the target behavior for phase 2.

## Requirements

- Docker or Podman with Testcontainers-compatible access
- Project dependencies installed (`poetry install`)

The Prism spec is injected into the container at startup, so this works with a
remote daemon as well as a local engine.

## Run

```bash
make pytest-integration
```

## OpenAPI fixture

The Prism mock reads this checked-in fixture:

- `tests/fixtures/user-portal.openapi.yaml`

The fixture is a manual snapshot. Update it manually when the upstream contract
changes. The authoritative source URL is documented at the top of that file.
