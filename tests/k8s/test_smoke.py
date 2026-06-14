"""Smoke tests for the deployed ska-oso-services Helm release.

These verify the *deployment plumbing* — that the chart rendered, the image
started, routing works, and the app can reach its Postgres.  Business logic
integration tests live in ``tests/component/`` and run against a
testcontainer Postgres instead.
"""

# pylint: disable=missing-timeout
from http import HTTPStatus

import requests

from .conftest import _expect_ok


def test_openapi_reachable(service_url):
    """The deployed pod serves its OpenAPI document."""
    response = requests.get(f"{service_url}/openapi.json")
    _expect_ok(response)
    assert response.json()["info"]["title"]


def test_unauthenticated_endpoint(service_url):
    """An unauthenticated route returns 200 — confirms routing works."""
    response = requests.get(f"{service_url}/coordinates/N10/equatorial")
    _expect_ok(response)


def test_create_and_get_project_round_trip(service_url, auth_headers):
    """Service ↔ Postgres networking: POST a project, then GET it back."""
    create = requests.post(f"{service_url}/odt/prjs", headers=auth_headers)
    _expect_ok(create)
    prj_id = create.json()["prj_id"]
    assert prj_id.startswith("prj-")

    fetched = requests.get(f"{service_url}/odt/prjs/{prj_id}", headers=auth_headers)
    _expect_ok(fetched)
    assert fetched.json()["prj_id"] == prj_id


def test_forbidden_without_token(service_url):
    """A secured route rejects requests without an Authorization header."""
    response = requests.get(f"{service_url}/odt/sbds/create")
    assert response.status_code in (
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
    ), f"expected 401/403, got {response.status_code}: {response.text}"
