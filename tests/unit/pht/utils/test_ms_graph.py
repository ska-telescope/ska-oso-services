from unittest import mock

import pytest

from ska_oso_services.pht.utils.constants import MS_GRAPH_URL
from ska_oso_services.pht.utils.ms_graph import make_graph_call


class TestMakeGraphCall:
    @mock.patch("ska_oso_services.pht.utils.ms_graph.client.acquire_token_silent")
    @mock.patch("ska_oso_services.pht.utils.ms_graph.client.acquire_token_for_client")
    @mock.patch("ska_oso_services.pht.utils.ms_graph.requests.get")
    def test_graph_call(
        self, mock_get, mock_acquire_token_for_client, mock_acquire_token_silent
    ):
        mock_acquire_token_silent.return_value = None
        mock_acquire_token_for_client.return_value = {"access_token": "fake-token"}

        mock_get.return_value.json.return_value = {
            "value": [{"id": "1", "name": "Username"}]
        }

        results = make_graph_call(f"{MS_GRAPH_URL}/users")

        assert len(results) == 1
        assert results[0]["name"] == "Username"

    @mock.patch("ska_oso_services.pht.utils.ms_graph.client.acquire_token_silent")
    @mock.patch("ska_oso_services.pht.utils.ms_graph.requests.get")
    def test_pagination(self, mock_get, mock_acquire_token_silent):
        mock_acquire_token_silent.return_value = {"access_token": "mock-token"}

        next_link = f"{MS_GRAPH_URL}users?$skiptoken=abc"
        mock_get.side_effect = [
            mock.Mock(
                json=lambda: {
                    "value": [{"id": "1"}],
                    "@odata.nextLink": next_link,
                }
            ),
            mock.Mock(json=lambda: {"value": [{"id": "2"}]}),
        ]

        results = make_graph_call(f"{MS_GRAPH_URL}/users")

        ids = [r["id"] for r in results]
        assert ids == ["1", "2"]

    @mock.patch("ska_oso_services.pht.utils.ms_graph.client.acquire_token_silent")
    def test_token_failure(self, mock_acquire_token_silent):
        mock_acquire_token_silent.return_value = {
            "error": "invalid_client",
            "error_description": "Error desc",
        }

        with pytest.raises(
            RuntimeError, match="Failed to acquire token: invalid_client"
        ):
            make_graph_call(f"{MS_GRAPH_URL}/v1.0/users")

    @mock.patch("ska_oso_services.pht.utils.ms_graph.client.acquire_token_silent")
    @mock.patch("ska_oso_services.pht.utils.ms_graph.requests.get")
    def test_request_error(self, mock_get, mock_acquire_token_silent):
        mock_acquire_token_silent.return_value = {"access_token": "fake-token"}
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(RuntimeError, match="Error fetching data from Graph API"):
            make_graph_call(f"{MS_GRAPH_URL}v1.0/users")
