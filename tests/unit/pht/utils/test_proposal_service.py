from unittest import mock

import pytest

from ska_oso_services.pht.service import proposal_service
from tests.unit.util import TestDataFactory


class TestRequirePerm:
    def test_allows_when_permission_present(self):
        """
        If any row contains the required permission, the function should:
        - NOT log a 'Forbidden' message
        - NOT raise an exception
        """
        rows = [TestDataFactory.proposal_access(permissions=["update"])]

        with mock.patch.object(proposal_service, "logger") as mock_logger:
            proposal_service._require_perm(
                rows=rows,
                required=proposal_service.ProposalPermissions.Update,
                action="update",
                prsl_id="prsl-123",
                user_id="user-42",
            )
            mock_logger.info.assert_not_called()

    @pytest.mark.parametrize(
        "rows",
        [
            [],  # no rows -> forbidden
            [
                TestDataFactory.proposal_access(permissions=[])
            ],  # empty list -> forbidden
            # wrong permission present -> forbidden
            # (requesting 'submit', row has only 'update')
            [TestDataFactory.proposal_access(permissions=["update"])],
        ],
        ids=["no_rows", "empty_perm_list", "wrong_perm_present"],
    )
    def test_raises_and_logs_when_missing(self, rows):
        """
        When the required permission is missing across all rows:
        - it should log one 'Forbidden ...' message
        - and raise ForbiddenError with a helpful detail
        """
        action = "submit"
        prsl_id = "prsl-999"
        user_id = "user-007"

        with mock.patch.object(proposal_service, "logger") as mock_logger:
            with pytest.raises(proposal_service.ForbiddenError) as exc:
                proposal_service._require_perm(
                    rows=rows,
                    required=proposal_service.ProposalPermissions.Submit,
                    action=action,
                    prsl_id=prsl_id,
                    user_id=user_id,
                )

            mock_logger.info.assert_called_once_with(
                "Forbidden %s attempt for proposal=%s by user_id=%s",
                action,
                prsl_id,
                user_id,
            )

            msg = str(getattr(exc.value, "detail", exc.value)).lower()
            assert "do not have access" in msg
            assert action in msg
            assert prsl_id in msg
