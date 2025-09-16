"""
Unit tests for ska_oso_pht_services.api
"""

from http import HTTPStatus
from unittest import mock

import pytest
from ska_aaa_authhelpers.roles import Role

from ska_oso_services.pht.api.reviewers import get_reviewers
from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import REVIEWERS

REVIEWERS_API_URL = f"{PHT_BASE_API_URL}/reviewers"


class TestGetReviewersEndpoint:
    @pytest.mark.parametrize(
        "sci_mock, tech_mock, expected_response",
        [
            (
                [
                    {
                        "@odata.type": "#microsoft.graph.user",
                        "id": "1",
                        "mail": "sci1@example.com",
                    }
                ],
                [
                    {
                        "@odata.type": "#microsoft.graph.user",
                        "id": "2",
                        "mail": "tech1@example.com",
                    }
                ],
                {
                    "sci_reviewers": [
                        {
                            "@odata.type": "#microsoft.graph.user",
                            "id": "1",
                            "mail": "sci1@example.com",
                        }
                    ],
                    "tech_reviewers": [
                        {
                            "@odata.type": "#microsoft.graph.user",
                            "id": "2",
                            "mail": "tech1@example.com",
                        }
                    ],
                },
            ),
            (
                [],
                [],
                {"sci_reviewers": [], "tech_reviewers": []},
            ),
        ],
    )
    @mock.patch("ska_oso_services.pht.utils.ms_graph.make_graph_call")
    def test_get_reviewers_success(
        self, mock_make_graph_call, sci_mock, tech_mock, expected_response, client
    ):
        mock_make_graph_call.side_effect = [sci_mock, tech_mock]

        response = client.get(f"{PHT_BASE_API_URL}/reviewers")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == expected_response
        assert mock_make_graph_call.call_count == 2
