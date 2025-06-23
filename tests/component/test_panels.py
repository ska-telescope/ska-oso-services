from http import HTTPStatus

import requests

from ..unit.util import TestDataFactory
from . import PHT_URL

PANELS_API_URL = f"{PHT_URL}/panels"
HEADERS = {"Content-type": "application/json"}

VALID_REVIEWER_ID = "c8f8f18a-3c70-4c39-8ed9-2d8d180d99a1"


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
    expected = {"detail": "Duplicates present in reviewers collection"}
    assert expected == result


def test_panels_post_duplicate_proposal():
    panel = TestDataFactory.panel(reviewer_id=VALID_REVIEWER_ID)
    panel.proposals.append(panel.proposals[0])

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.CONFLICT

    result = response.json()
    expected = {"detail": "Duplicates present in proposals collection"}
    assert expected == result


def test_panels_post_not_existing_reviewer():
    panel = TestDataFactory.panel()

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.BAD_REQUEST

    result = response.json()
    expected = {"detail": "Not existing reviewer detected: rev-001"}
    assert expected == result


def test_panels_post_not_existing_proposal():
    panel = TestDataFactory.panel(reviewer_id=VALID_REVIEWER_ID)

    data = panel.json()

    response = requests.post(f"{PANELS_API_URL}", data=data, headers=HEADERS)

    assert response.status_code == HTTPStatus.BAD_REQUEST

    result = response.json()
    expected = {"detail": "Not existing proposal detected: prop-astro-01"}
    assert expected == result
