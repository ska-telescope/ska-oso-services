from http import HTTPStatus

import requests

from ..unit.util import REVIEWERS, TestDataFactory
from . import PHT_URL

PANELS_API_URL = f"{PHT_URL}/panels"
HEADERS = {"Content-type": "application/json"}


def test_create_panel():
    panel = TestDataFactory.panel_basic()
    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.OK

    result = response.json()
    assert panel.panel_id == result


def test_panels_post_duplicate_reviewer():
    panel = TestDataFactory.panel()
    panel.reviewers.append(panel.reviewers[0])

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.CONFLICT

    result = response.json()
    expected = {"detail": "Duplicate reviewer_id are not allowed: {'rev-001'}"}
    assert expected == result


def test_panels_post_duplicate_proposal():
    panel = TestDataFactory.panel(reviewer_id=REVIEWERS[0]["id"])
    panel.proposals.append(panel.proposals[0])

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.CONFLICT

    result = response.json()
    expected = {"detail": "Duplicate prsl_id are not allowed: {'prop-astro-01'}"}
    assert expected == result


def test_panels_post_not_existing_reviewer():
    panel = TestDataFactory.panel()

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.BAD_REQUEST

    result = response.json()
    expected = {"detail": "Reviewer 'rev-001' does not exist"}
    assert expected == result


def test_panels_post_not_existing_proposal():
    panel = TestDataFactory.panel(reviewer_id=REVIEWERS[0]["id"])

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.BAD_REQUEST

    result = response.json()
    expected = {"detail": "Proposal 'prop-astro-01' does not exist"}
    assert expected == result
