"""
Unit tests for ska_oso_pht_services.api
"""

import json
from http import HTTPStatus
from types import SimpleNamespace
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from ska_db_oda.persistence.domain.errors import ODANotFound

from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import VALID_REVIEW, TestDataFactory, assert_json_is_equal

REVIEWS_API_URL = f"{PHT_BASE_API_URL}/reviews"


class TestReviewCreateAPI:

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_create_review_creates_new_success(self, mock_oda, client):
        """
        When no existing review matches, it should create one,
        commit, and return review_id.
        """
        review_obj = TestDataFactory.reviews()
        uow = mock.MagicMock()
        uow.rvws.query.return_value = []
        uow.rvws.add.return_value = review_obj
        mock_oda.return_value.__enter__.return_value = uow

        resp = client.post(
            f"{REVIEWS_API_URL}/create",
            data=VALID_REVIEW,
            headers={"Content-type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.OK
        assert resp.json() == review_obj.review_id
        uow.rvws.query.assert_called_once()
        uow.rvws.add.assert_called_once()
        uow.commit.assert_called_once()

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_create_review_returns_existing_when_version_1(self, mock_oda, client):
        """
        If an existing review with version==1 is found,
        it should return its review_id without creating a new one.
        """
        existing = TestDataFactory.reviews()
        if getattr(existing, "metadata", None) is None:
            existing.metadata = SimpleNamespace(version=1)
        else:
            existing.metadata.version = 1

        uow = mock.MagicMock()
        uow.rvws.query.return_value = [existing]
        mock_oda.return_value.__enter__.return_value = uow

        resp = client.post(
            f"{REVIEWS_API_URL}/create",
            data=VALID_REVIEW,
            headers={"Content-type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.OK

        assert resp.json() == existing.review_id
        uow.rvws.add.assert_not_called()
        uow.commit.assert_not_called()

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_create_review_existing_not_version1_creates_new(self, mock_oda, client):
        """
        If existing review exists but version != 1,
          it should create a new one.
        """
        existing = TestDataFactory.reviews()
        if getattr(existing, "metadata", None) is None:
            existing.metadata = SimpleNamespace(version=2)
        else:
            existing.metadata.version = 2

        created = TestDataFactory.reviews()
        uow = mock.MagicMock()
        uow.rvws.query.return_value = [existing]
        uow.rvws.add.return_value = created
        mock_oda.return_value.__enter__.return_value = uow

        resp = client.post(
            f"{REVIEWS_API_URL}/create",
            data=VALID_REVIEW,
            headers={"Content-type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.OK
        assert resp.json() == created.review_id
        uow.rvws.add.assert_called_once()
        uow.commit.assert_called_once()

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_create_review_value_error_raises_bad_request(self, mock_oda, client):
        """
        Value Error during add()
        """
        uow = mock.MagicMock()
        uow.rvws.query.return_value = []
        uow.rvws.add.side_effect = ValueError("mock-failure")
        mock_oda.return_value.__enter__.return_value = uow

        resp = client.post(
            f"{REVIEWS_API_URL}/create",
            data=VALID_REVIEW,
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == HTTPStatus.BAD_REQUEST, resp.text
        detail = resp.json().get("detail", "")
        assert "Failed when attempting to create a Review" in detail
        assert "mock-failure" in detail

        uow.rvws.query.assert_called_once()
        uow.rvws.add.assert_called_once()
        uow.commit.assert_not_called()


# class TestGetReviewAPI:
#       @mock.patch("ska_oso_services.pht.api.prsls.oda.uow", autospec=True)
#     def test_get_reviews_for_proposal_with_wrong_id(self, mock_oda, client):
#         """
#         Test reviews for a proposal with a wrong ID returns an empty list.
#         """
#         uow_mock = mock.MagicMock()
#         uow_mock.rvws.query.return_value = []
#         mock_oda.return_value.__enter__.return_value = uow_mock

#         prsl_id = "wrong id"
#         response = client.get(f"{PROPOSAL_API_URL}/reviews/{prsl_id}")

#         assert response.status_code == HTTPStatus.OK
#         assert response.json() == []

#     @mock.patch("ska_oso_services.pht.api.prsls.oda.uow")
#     def test_get_reviews_for_panel_with_valid_id(self, mock_oda, client):
#         """
#         Test reviews for a proposal with a valid ID returns the expected reviews.
#         """
#         review_objs = [TestDataFactory.reviews(prsl_id="my proposal")]
#         uow_mock = mock.MagicMock()
#         uow_mock.rvws.query.return_value = review_objs
#         mock_oda.return_value.__enter__.return_value = uow_mock

#         prsl_id = "my proposal"
#         response = client.get(f"{PROPOSAL_API_URL}/reviews/{prsl_id}")
#         assert response.status_code == HTTPStatus.OK

#         expected = [
#             obj.model_dump(mode="json", exclude={"metadata"}) for obj in review_objs
#         ]
#         payload = response.json()
#         # align shapes by dropping metadata
#         del payload[0]["metadata"]
#         assert expected == payload
#         assert payload[0]["review_id"] == expected[0]["review_id"]
#         assert payload[0]["panel_id"] == expected[0]["panel_id"]


class TestReviewAPI:

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_get_review_not_found(self, mock_oda, client):
        """
        Ensure ODANotFound during get() raises NotFoundError (404).
        """
        review_id = "prsl-missing-9999"

        uow_mock = mock.MagicMock()
        uow_mock.rvws.get.side_effect = ODANotFound(identifier=review_id)
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{REVIEWS_API_URL}/{review_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "could not be found" in response.json()["detail"]

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_get_review_success(self, mock_oda, client):
        """
        Ensure valid review ID returns the review object.
        """
        review = TestDataFactory.reviews()
        review_id = review.review_id

        uow_mock = mock.MagicMock()
        uow_mock.rvws.get.return_value = review
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{REVIEWS_API_URL}/{review_id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["review_id"] == review_id

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_get_review_list_success(self, mock_oda, client):
        """
        Check if the get_reviews_for_user returns reviews correctly.
        """
        review_objs = [TestDataFactory.reviews(), TestDataFactory.reviews()]
        uow_mock = mock.MagicMock()
        uow_mock.rvws.query.return_value = review_objs
        mock_oda.return_value.__enter__.return_value = uow_mock

        user_id = "DefaultUser"
        response = client.get(f"{REVIEWS_API_URL}/users/{user_id}/reviews")
        assert response.status_code == HTTPStatus.OK
        assert isinstance(response.json(), list)
        assert len(response.json()) == len(review_objs)

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_get_review_list_none(self, mock_oda, client):
        """
        Should return empty list if no reviews are found.
        """
        uow_mock = mock.MagicMock()
        uow_mock.rvws.query.return_value = []
        mock_oda.return_value.__enter__.return_value = uow_mock

        user_id = "user123"
        response = client.get(f"{REVIEWS_API_URL}/users/{user_id}/reviews")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == []

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_review_put_success(self, mock_uow, client):
        """
        Check the rvws_put method returns the expected response
        """
        uow_mock = mock.MagicMock()
        uow_mock.prsl.__contains__.return_value = True
        review_obj = TestDataFactory.reviews()
        review_id = review_obj.review_id
        uow_mock.rvws.add.return_value = review_obj
        uow_mock.rvws.get.return_value = review_obj
        mock_uow().__enter__.return_value = uow_mock

        result = client.put(
            f"{REVIEWS_API_URL}/{review_id}",
            data=review_obj.model_dump_json(),
            headers={"Content-type": "application/json"},
        )

        assert result.status_code == HTTPStatus.OK
        assert_json_is_equal(result.text, review_obj.model_dump_json())

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_update_review_not_found(self, mock_uow, client):
        """
        Should return 404 if review doesn't exist.
        """
        review_obj = TestDataFactory.reviews()
        review_id = review_obj.review_id

        uow_mock = mock.MagicMock()
        uow_mock.rvws.get.return_value = None  # not found
        mock_uow.return_value.__enter__.return_value = uow_mock

        response = client.put(
            f"{REVIEWS_API_URL}/{review_id}",
            data=review_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_update_review_id_mismatch(self, mock_uow, client):
        """
        Should raise 422 when ID in path != payload.
        """
        review_obj = TestDataFactory.reviews()
        path_id = "diff-id"

        response = client.put(
            f"{REVIEWS_API_URL}/{path_id}",
            data=review_obj.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "do not match" in response.json()["detail"].lower()
