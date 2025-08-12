from datetime import datetime, timezone

from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal import Proposal

from ska_oso_services.common.error_handling import ForbiddenError
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

    investigator_refs = [inv.investigator_id for inv in data.info.investigators]

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
) -> None:
    """
    Ensure the user has at least 'view' permission for the given proposal.
    Raises ForbiddenError if not allowed.
    """
    rows_init = uow.prslacc.query(CustomQuery(user_id=user_id, prsl_id=prsl_id)) or []
    rows = get_latest_entity_by_id(rows_init, "access_id") or []
    access = rows[0] if rows else None
    if not access:
        raise ForbiddenError(detail="You do not have access to this proposal.")
