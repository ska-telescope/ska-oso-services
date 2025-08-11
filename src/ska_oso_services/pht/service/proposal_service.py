from datetime import datetime, timezone

from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal import Proposal, ProposalPermissions

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
    uow, user_id: str, prsl_id: str, action: ProposalPermissions
) -> None:
    """
    Ensures the user has the specified permission for the given proposal.
    Raises ForbiddenError if not allowed.
    """
    rows = get_latest_entity_by_id(
        uow.prslacc.query(CustomQuery(user_id=user_id, prsl_id=prsl_id)), "access_id"
    )
    access = rows[0] if rows else None
    if not access:
        raise ForbiddenError(detail="You do not have access to this proposal.")

    perms = access.permissions or []
    norm = {
        p.value if isinstance(p, ProposalPermissions) else str(p).lower() for p in perms
    }
    needed = (
        action.value if isinstance(action, ProposalPermissions) else str(action).lower()
    )

    if needed not in norm:
        raise ForbiddenError(
            detail="You do not have permission to perform this action."
        )


def list_accessible_proposal_ids(
    uow, user_id: str, required_perm: ProposalPermissions = ProposalPermissions.View
) -> list[str]:
    """
    Return all proposal IDs a user can access.
    """
    rows = (
        get_latest_entity_by_id(
            uow.prslacc.query(CustomQuery(user_id=user_id)), "access_id"
        )
        or []
    )
    needed = required_perm.value
    return list(
        {
            row.prsl_id
            for row in rows
            if any(
                (p.value if isinstance(p, ProposalPermissions) else str(p).lower())
                == needed
                for p in (row.permissions or [])
            )
        }
    )
