"""Shared testcontainers fixtures for integration tests.

Starts a session-scoped Postgres container running the pre-migrated
``oda-test-db`` image (built by ska-db-oda).  Because the image already has
every Liquibase changeset applied, no migration step is needed in tests.

The fixture sets the standard ``PG*`` environment variables so that
``ska_db_oda.unitofwork.postgresunitofwork.get_conninfo()`` connects to the
container with no application-code changes.

Podman
------
Configure the socket and disable Ryuk before invoking pytest::

    export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
    export TESTCONTAINERS_RYUK_DISABLED=true
"""

from __future__ import annotations

import os

import pytest
from psycopg import sql as psql
from testcontainers.postgres import PostgresContainer

_DEFAULT_ODA_TEST_DB_IMAGE = (
    "registry.gitlab.com/ska-telescope/db/ska-db-oda/oda-test-db:e3b7519b"
)
# Pinned tag — bump when ska-db-oda publishes a newer build, or override via
# the env var to test against a different image without editing source.
ODA_TEST_DB_IMAGE = os.environ.get("ODA_TEST_DB_IMAGE", _DEFAULT_ODA_TEST_DB_IMAGE)

_DEFAULT_DB = "oda"
_DEFAULT_USER = "oda_admin"
_DEFAULT_PASSWORD = "testpassword"

# Tables written by the ODA / OSO-services code under test.  Listed explicitly
# (rather than `TRUNCATE ALL`) because the oda-test-db image seeds enum-like
# lookup tables (`proposal.pm_*_statuses`, `proposal.proposal_roles`,
# `schedule.queue_statuses`, `status.valid_statuses`) that the application
# depends on and must NOT be cleared between tests.  Liquibase's own
# `databasechangelog`/`databasechangeloglock` tables are also preserved.
_TABLES_TO_TRUNCATE = (
    "execution.execution_blocks",
    "execution.sb_instances",
    "project.sb_definition_history",
    "project.sb_definitions",
    "project.observing_blocks",
    "project.projects",
    "proposal.reviews",
    "proposal.panel_decisions",
    "proposal.panels",
    "proposal.access_tmp",
    "proposal.proposals",
    "schedule.observing_queue_items",
    "schedule.observing_queues",
    "shift_log.annotations",
    "shift_log.comment_replies",
    "shift_log.comments_history",
    "shift_log.comments",
    "shift_log.logs",
    "shift_log.shifts",
    "shift_log.tags",
    "status.status_entries",
)


@pytest.fixture(scope="session")
def postgres_container():
    """Start a Postgres container, or reuse an external one if ``PGHOST`` is set.

    Sets ``PGHOST``, ``PGPORT``, ``PGDATABASE``, ``PGUSER``, and ``PGPASSWORD``
    so the application's ``PostgresUnitOfWork`` connects to it transparently.
    """
    if os.environ.get("PGHOST"):
        # External Postgres provided (e.g. CI `services:` block).  Use it.
        yield None
        return

    container = PostgresContainer(
        image=ODA_TEST_DB_IMAGE,
        username=_DEFAULT_USER,
        password=_DEFAULT_PASSWORD,
        dbname=_DEFAULT_DB,
        driver=None,
    )

    with container:
        os.environ["PGHOST"] = container.get_container_host_ip()
        os.environ["PGPORT"] = str(container.get_exposed_port(5432))
        os.environ["PGDATABASE"] = _DEFAULT_DB
        os.environ["PGUSER"] = _DEFAULT_USER
        os.environ["PGPASSWORD"] = _DEFAULT_PASSWORD

        yield container

        for var in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"):
            os.environ.pop(var, None)


@pytest.fixture
def clean_db(postgres_container):  # pylint: disable=unused-argument
    """Truncate ODA tables after each test for isolation.

    Lookup/seed tables are preserved.  ``CASCADE`` handles FK chains;
    ``RESTART IDENTITY`` resets autoincrement sequences so skuid-style IDs
    do not collide across tests.
    """
    yield
    from ska_db_oda.unitofwork.postgresunitofwork import PostgresUnitOfWork

    with PostgresUnitOfWork() as uow:
        statement = psql.SQL("TRUNCATE {tables} RESTART IDENTITY CASCADE").format(
            tables=psql.SQL(", ").join(
                psql.Identifier(*tbl.split(".")) for tbl in _TABLES_TO_TRUNCATE
            )
        )
        uow._conn.execute(statement)  # pylint: disable=protected-access
        uow.commit()
