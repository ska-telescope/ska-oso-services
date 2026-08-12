from contextlib import nullcontext
from unittest.mock import MagicMock, Mock

import pytest
from ska_aaa_authhelpers import AuthContext, AuthFailError

from ska_oso_services.pht.service.security.facts import Facts
from ska_oso_services.pht.service.security.rules.reviews import ReviewRules
from tests.unit.util import TestDataFactory

USER_ID = "a1baebc7-2d1a-4a35-ac07-478d2fc6af95"
OTHER_USER_ID = "b2cbfcd8-3e2b-5b46-bd18-589f7d3fb0a6"


def mock_facts(*, is_pht_admin: bool = False, user_id: str = USER_ID) -> Mock:
    facts = Mock(spec=Facts)
    facts.auth = MagicMock(spec=AuthContext)
    facts.auth.user_id = user_id
    facts.is_pht_admin.return_value = is_pht_admin
    return facts


@pytest.mark.parametrize(
    ("facts", "reviewer_id", "expectation"),
    [
        pytest.param(
            mock_facts(is_pht_admin=True),
            OTHER_USER_ID,
            nullcontext(),
            id="allow-pht-admin-edit-any-review",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, user_id=USER_ID),
            USER_ID,
            nullcontext(),
            id="allow-assigned-reviewer-edit-own-review",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, user_id=USER_ID),
            OTHER_USER_ID,
            pytest.raises(AuthFailError, match="Only the reviewer"),
            id="deny-non-assigned-reviewer",
        ),
    ],
)
def test_allowed_to_edit(facts, reviewer_id, expectation):
    # science vs technical is a per-review attribute now, not a user role,
    # so both kinds of review should be governed by the same ownership rule
    review = TestDataFactory.reviews(reviewer_id=reviewer_id)
    rules = ReviewRules(facts)

    with expectation:
        rules.allowed_to_edit(review)


@pytest.mark.parametrize(
    ("facts", "expectation"),
    [
        pytest.param(mock_facts(is_pht_admin=True), nullcontext(), id="allow-pht-admin"),
        pytest.param(
            mock_facts(is_pht_admin=False),
            pytest.raises(AuthFailError, match="cannot view reviews"),
            id="deny-non-admin",
        ),
    ],
)
def test_allowed_to_view(facts, expectation):
    rules = ReviewRules(facts)

    with expectation:
        rules.allowed_to_view("rvw-1", "rvw-2")
