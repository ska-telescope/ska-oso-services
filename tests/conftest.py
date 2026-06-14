"""Top-level pytest configuration.

Registers the shared testcontainers fixtures (``postgres_container``,
``clean_db``) so any test suite that needs a Postgres can use them.

The fixtures themselves are session-/function-scoped, so suites that don't
ask for them (e.g. ``tests/unit/`` which mocks the UoW, or ``tests/live/``
which targets a remote service) pay no startup cost.
"""

pytest_plugins = ["tests.db_fixtures"]
