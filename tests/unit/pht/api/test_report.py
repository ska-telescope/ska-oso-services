from http import HTTPStatus
from unittest import mock

from ska_db_oda.persistence.domain.errors import ODANotFound

from tests.unit.conftest import PHT_BASE_API_URL
from tests.unit.util import REVIEWERS, TestDataFactory

REPORT_API_URL = f"{PHT_BASE_API_URL}/report"
HEADERS = {"Content-type": "application/json"}


class TestReportsAPI:
    @mock.patch("ska_oso_services.pht.api.report.oda.uow", autospec=True)
    def test_get_report_success(self, mock_uow, client):
        mock_proposals = [
            TestDataFactory.complete_proposal(prsl_id="prsl-mvp01-20220923-00001")
        ]
        mock_panels = [
            TestDataFactory.panel(
                prsl_id_1=mock_proposals[0].prsl_id, reviewer_id=REVIEWERS[0]["id"]
            )
        ]
        mock_reviews = [
            TestDataFactory.reviews(
                prsl_id=mock_proposals[0].prsl_id,
                reviewer_id=REVIEWERS[0]["id"],
                review_id="rvw-mvp01-20220923-00001",
            )
        ]
        mock_decisions = [
            TestDataFactory.panel_decision(prsl_id=mock_proposals[0].prsl_id)
        ]
        mock_report = [
            TestDataFactory.proposal_report(
                prsl_id=mock_proposals[0].prsl_id,
                panel_id=mock_panels[0].panel_id,
                reviewer_id=REVIEWERS[0]["id"],
            )
        ]  # a list of dict

        # Setup oda.uow context manager
        uow_mock = mock.MagicMock()
        uow_mock.prsls.query.return_value = "proposal_query"
        uow_mock.panels.query.return_value = "panel_query"
        uow_mock.rvws.query.return_value = "review_query"
        uow_mock.pnlds.query.return_value = "decision_query"
        mock_uow.return_value.__enter__.return_value = uow_mock

        with (
            mock.patch(
                "ska_oso_services.pht.api.report.get_latest_entity_by_id"
            ) as mock_get_latest,
            mock.patch(
                "ska_oso_services.pht.api.report.join_proposals_panels_reviews_decisions"  # noqa: E501
            ) as mock_join,
        ):
            mock_get_latest.side_effect = [
                mock_proposals,
                mock_panels,
                mock_reviews,
                mock_decisions,
            ]
            mock_join.return_value = mock_report

            response = client.get(f"{REPORT_API_URL}/")

        assert response.status_code == HTTPStatus.OK

        result = response.json()
        assert result[0]["prsl_id"] == mock_report[0]["prsl_id"]
        assert result[0]["panel_id"] == mock_report[0]["panel_id"]
        assert result[0]["reviewer_id"] == mock_report[0]["reviewer_id"]
        assert result[0]["review_id"] == mock_report[0]["review_id"]
