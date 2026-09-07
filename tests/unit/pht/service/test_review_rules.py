from contextlib import nullcontext
from unittest.mock import MagicMock, Mock

import pytest
from ska_aaa_authhelpers import AuthContext, AuthFailError

from ska_oso_services.pht.service.security.facts import Facts
from ska_oso_services.pht.service.security.rules.reviews import ReviewRules
from tests.unit.util import TestDataFactory


def mock_facts(
    *,
    is_pht_admin: bool = False,
    is_me: bool = False,
    is_chair: bool = False,
    is_member: bool = True,
) -> Mock:
    facts = Mock(spec=Facts)
    facts.auth = MagicMock(spec=AuthContext)
    facts.is_pht_admin.return_value = is_pht_admin
    facts.is_chair.return_value = is_chair
    facts.is_member_of.return_value = is_member
    facts.is_me.return_value = is_me
    return facts


@pytest.mark.parametrize(
    ("facts", "expectation"),
    [
        pytest.param(
            mock_facts(is_pht_admin=True, is_me=False, is_member=False),
            nullcontext(),
            id="allow-pht-admin-create-any-review",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_me=True, is_member=True),
            nullcontext(),
            id="allow-assigned-member-create-own-review",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_me=True, is_member=False),
            pytest.raises(AuthFailError, match="Only members of the panel"),
            id="deny-me-if-not-member-of-panel",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_me=False, is_member=True),
            pytest.raises(AuthFailError, match="Only members of the panel"),
            id="deny-non-me-even-if-member-of-panel",
        ),
    ],
)
def test_allowed_to_create(facts, expectation):
    review = TestDataFactory.reviews()
    rules = ReviewRules(facts)

    with expectation:
        rules.allowed_to_create(review)


@pytest.mark.parametrize(
    ("facts", "expectation"),
    [
        pytest.param(
            mock_facts(is_pht_admin=True, is_me=False),
            nullcontext(),
            id="allow-pht-admin-edit-any-review",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_me=True),
            nullcontext(),
            id="allow-assigned-reviewer-edit-own-review",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_me=False),
            pytest.raises(AuthFailError, match="Only the reviewer"),
            id="deny-non-assigned-reviewer",
        ),
    ],
)
def test_allowed_to_edit(facts, expectation):
    review = TestDataFactory.reviews()
    rules = ReviewRules(facts)

    with expectation:
        rules.allowed_to_edit(review)


@pytest.mark.parametrize(
    ("facts", "expectation"),
    [
        pytest.param(
            mock_facts(is_pht_admin=True, is_me=False),
            nullcontext(),
            id="allow-pht-admin",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_me=True),
            nullcontext(),
            id="allow-review-author",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_me=False, is_chair=True),
            nullcontext(),
            id="allow-panel-chair",
        ),
        pytest.param(
            mock_facts(is_pht_admin=False, is_me=False, is_chair=False),
            pytest.raises(AuthFailError, match="Only the author"),
            id="deny-other-users",
        ),
    ],
)
def test_allowed_to_view(facts, expectation):
    review = TestDataFactory.reviews()
    rules = ReviewRules(facts)
    with expectation:
        rules.allowed_to_view(review)
