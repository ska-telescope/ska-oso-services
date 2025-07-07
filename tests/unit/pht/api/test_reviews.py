"""
Unit tests for ska_oso_pht_services.api
"""

import json
from http import HTTPStatus
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status

from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import VALID_REVIEW, TestDataFactory, assert_json_is_equal

REVIEWS_API_URL = f"{PHT_BASE_API_URL}/reviews"


class TestReviewAPI:
    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_create_review(self, mock_oda, client):
        """
        Check the review_create method returns the expected review_id and status code.
        """

        review_obj = TestDataFactory.reviews()

        uow_mock = mock.MagicMock()
        uow_mock.rvws.add.return_value = review_obj
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{REVIEWS_API_URL}/create",
            data=VALID_REVIEW,
            headers={"Content-type": "application/json"},
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json() == review_obj.review_id

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_create_review_value_error_raises_bad_request(self, mock_oda, client):
        """
        Simulate ValueError in review creation and ensure it raises BadRequestError.
        """

        uow_mock = mock.MagicMock()
        uow_mock.rvws.add.side_effect = ValueError("mock-failure")

        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.post(
            f"{REVIEWS_API_URL}/create",
            data=VALID_REVIEW,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "Failed when attempting to create a Review" in data["detail"]

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_get_review_not_found(self, mock_oda, client):
        """
        Ensure KeyError during get() raises NotFoundError (404).
        """
        review_id = "prsl-missing-9999"

        uow_mock = mock.MagicMock()
        uow_mock.rvws.get.side_effect = KeyError(review_id)
        mock_oda.return_value.__enter__.return_value = uow_mock

        response = client.get(f"{REVIEWS_API_URL}/{review_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "Could not find Review" in response.json()["detail"]

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
        response = client.get(f"{REVIEWS_API_URL}/list/{user_id}")
        assert response.status_code == HTTPStatus.OK
        assert isinstance(response.json(), list)
        assert len(response.json()) == len(review_objs)

    @mock.patch("ska_oso_services.pht.api.reviews.oda.uow", autospec=True)
    def test_get_review_list_none(self, mock_oda, client):
        """
        Should return empty list if no reviews are found.
        """
        uow_mock = mock.MagicMock()
        uow_mock.rvws.query.return_value = None
        mock_oda.return_value.__enter__.return_value = uow_mock

        user_id = "user123"
        response = client.get(f"{REVIEWS_API_URL}/list/{user_id}")

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
