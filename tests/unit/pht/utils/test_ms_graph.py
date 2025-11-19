from types import SimpleNamespace
from unittest import mock

import jwt
import pytest

from ska_oso_services.pht.utils.constants import MS_GRAPH_URL
from ska_oso_services.pht.utils.ms_graph import (
    extract_profile_from_access_token,
    make_graph_call, _extract_pi_user_id
)

MODULE = "ska_oso_services.pht.utils.ms_graph"


class TestExtractTokenDetails:

    @mock.patch(f"{MODULE}.jwt.decode")
    def test_success_prefers_given_family_and_preferred_username(self, mock_decode):
        mock_decode.return_value = {
            "given_name": "Jane",
            "family_name": "Doe",
            "upn": "jane@example.com",
        }
        auth = SimpleNamespace(access_token="a.b.c")

        given, family, email = extract_profile_from_access_token(auth)

        assert (given, family, email) == ("Jane", "Doe", "jane@example.com")
        mock_decode.assert_called_once_with(
            "a.b.c", options={"verify_signature": False, "verify_exp": False}
        )

    @mock.patch(f"{MODULE}.jwt.decode")
    def test_bearer_prefix_is_stripped(self, mock_decode):
        mock_decode.return_value = {
            "given_name": "Bee",
            "family_name": "Rarer",
            "upn": "bearer@example.com",
        }
        auth = SimpleNamespace(access_token="Bearer aaa.bbb.ccc")

        given, family, email = extract_profile_from_access_token(auth)

        assert (given, family, email) == ("Bee", "Rarer", "bearer@example.com")
        mock_decode.assert_called_once_with(
            "aaa.bbb.ccc", options={"verify_signature": False, "verify_exp": False}
        )

    @mock.patch(f"{MODULE}.jwt.decode")
    def test_missing_access_token_returns_empty_triplet(self, mock_decode):
        mock_decode.side_effect = jwt.InvalidTokenError("empty")
        auth = SimpleNamespace(access_token="")

        given, family, email = extract_profile_from_access_token(auth)

        assert (given, family, email) == ("", "", "")
        mock_decode.assert_called_once()


class TestMakeGraphCall:
    @mock.patch(f"{MODULE}.client.acquire_token_silent")
    @mock.patch(f"{MODULE}.client.acquire_token_for_client")
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

    @mock.patch(f"{MODULE}.client.acquire_token_silent")
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

    @mock.patch(f"{MODULE}.client.acquire_token_silent")
    def test_token_failure(self, mock_acquire_token_silent):
        mock_acquire_token_silent.return_value = {
            "error": "invalid_client",
            "error_description": "Error desc",
        }

        with pytest.raises(
            RuntimeError, match="Failed to acquire token: invalid_client"
        ):
            make_graph_call(f"{MS_GRAPH_URL}/v1.0/users")

    @mock.patch(f"{MODULE}.client.acquire_token_silent")
    @mock.patch(f"{MODULE}.requests.get")
    def test_request_error(self, mock_get, mock_acquire_token_silent):
        mock_acquire_token_silent.return_value = {"access_token": "fake-token"}
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(RuntimeError, match="Error fetching data from Graph API"):
            make_graph_call(f"{MS_GRAPH_URL}v1.0/users")



class TestExtractPiUserId:
    def _make_proposal(self, investigators):
        proposal_info = SimpleNamespace(investigators=investigators)
        return SimpleNamespace(proposal_info=proposal_info)

    def test_returns_trimmed_user_id_for_pi(self):
        pi = SimpleNamespace(
            principal_investigator=True,
            user_id="  pi.user@example.com  ",
        )
        non_pi = SimpleNamespace(
            principal_investigator=False,
            user_id="other@example.com",
        )
        proposal = self._make_proposal([non_pi, pi])

        result = _extract_pi_user_id(proposal)

        assert result == "pi.user@example.com"

    def test_returns_none_when_proposal_info_missing(self):
        proposal = SimpleNamespace()
        result = _extract_pi_user_id(proposal)
        assert result is None

    def test_returns_none_when_investigators_missing_or_empty(self):
        proposal_info = SimpleNamespace(investigators=None)
        proposal = SimpleNamespace(proposal_info=proposal_info)
        assert _extract_pi_user_id(proposal) is None

        # investigators is empty list
        proposal_info2 = SimpleNamespace(investigators=[])
        proposal2 = SimpleNamespace(proposal_info=proposal_info2)
        assert _extract_pi_user_id(proposal2) is None

    def test_returns_none_when_no_principal_investigator(self):
        inv1 = SimpleNamespace(
            principal_investigator=False,
            user_id="user1@example.com",
        )
        inv2 = SimpleNamespace(
            principal_investigator=False,
            user_id="user2@example.com",
        )
        proposal = self._make_proposal([inv1, inv2])

        result = _extract_pi_user_id(proposal)

        assert result is None

    def test_returns_none_when_pi_has_no_user_id(self):
        # PI present but user_id is None
        pi = SimpleNamespace(
            principal_investigator=True,
            user_id=None,
        )
        proposal = self._make_proposal([pi])

        result = _extract_pi_user_id(proposal)
        assert result is None
