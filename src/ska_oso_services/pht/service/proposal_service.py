from datetime import datetime, timezone

from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal import Proposal, ProposalAccess

from ska_oso_services.common.error_handling import ForbiddenError
from ska_oso_services.pht.utils.constants import ACCESS_ID
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id


def transform_update_proposal(data: Proposal) -> Proposal:
    """
    Transforms and updates a given Proposal model.

    - If prsl_id is "new", sets it to "12345".
    - Sets submitted_on to now if submitted_by is provided.
    - Sets status based on presence of submitted_on.
    - Extracts investigator_refs from info.investigators.
    """

    # TODO : rethink the logic here - may need to move to UI
    if data.submitted_by:
        submitted_on = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = "submitted"
    else:
        submitted_on = data.submitted_on
        status = "submitted" if submitted_on else "draft"

    investigator_refs = [inv.user_id for inv in data.info.investigators]

    return Proposal(
        prsl_id=data.prsl_id,
        cycle=data.cycle,
        submitted_by=data.submitted_by,
        submitted_on=submitted_on,
        status=status,
        info=data.info,
        investigator_refs=investigator_refs,
    )


def assert_user_has_permission_for_proposal(
    uow,
    user_id: str,
    prsl_id: str,
) -> list[ProposalAccess]:
    """Asserts if the authenticated user has access to a
        specific proposal or raise ForbiddenError.

    Args:
        uow: Unit-of-work with `prslacc` repo access.
        user_id: The user identifier to check.
        prsl_id: Proposal identifier.

    Raises:
        ForbiddenError: If user has no access row for the given proposal.
    Returns:
        list[access]
    """
    rows = (
        get_latest_entity_by_id(
            uow.prslacc.query(CustomQuery(user_id=user_id, prsl_id=prsl_id)),
            ACCESS_ID,
        )
        or []
    )
    access = rows[0] if rows else None
    if not access:
        raise ForbiddenError(
            detail=f"You do not have access to this proposal with id:{prsl_id}"
        )
    return rows


def list_accessible_proposal_ids(uow, user_id: str) -> list[str]:
    """
    Return sorted unique proposal IDs accessible to a user.

    The function queries the proposal-access repository for all access rows
    that match the given user and then selects the latest entity per access_id,
    finally deduplicating and sorting by proposal id.

    Args:
        uow: Unit-of-work providing `prslacc` repo with a `query` method.
        user_id: The user identifier from the token of the authenticated user.

    Returns:
        List[str]: Sorted list of proposal IDs (may be empty).

    Notes:
        - No permission filtering beyond existence of access rows,
            given that every entry has the basic `view` access
        - Uses `get_latest_entity_by_id(rows, "access_id")`
            to retrive the latest version.
    """
    rows_init = uow.prslacc.query(CustomQuery(user_id=user_id)) or []
    rows = get_latest_entity_by_id(rows_init, ACCESS_ID) or []
    return sorted({row.prsl_id for row in rows})
