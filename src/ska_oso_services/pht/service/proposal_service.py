import logging
from datetime import date, datetime, time, timezone

from pydantic import ValidationError
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal import Proposal, ProposalAccess, ProposalPermissions
from ska_oso_pdm.proposal.proposal import ProposalStatus
from ska_oso_pdm.proposal_management.panel import ProposalAssignment

from ska_oso_services.common.error_handling import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
from ska_oso_services.pht.utils.constants import ACCESS_ID
from ska_oso_services.pht.utils.pht_helper import get_latest_entity_by_id

LOGGER = logging.getLogger(__name__)


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


def _require_perm(
    rows, required: ProposalPermissions, action: str, prsl_id: str, user_id: str
) -> None:
    if not any(required in r.permissions for r in rows):
        LOGGER.info(
            "Forbidden %s attempt for proposal=%s by user_id=%s",
            action,
            prsl_id,
            user_id,
        )
        raise ForbiddenError(
            detail=f"You do not have access to {action} proposal with id: {prsl_id}"
        )


def update_proposal_service(
    *, uow, prsl_id: str, payload: Proposal, user_id: str
) -> Proposal:
    """
    - DRAFT -> require Update; persist as-is.
    - SUBMITTED ->
        - require Submit;
        - if submitted_on >= CLOSE_ON: SKIP (no panel assignment, no status change/persist), return existing;
        - if submitted_on < CLOSE_ON:
            - assign to existing panel (prefer 'Science Verification', else by info.science_category);
            - if no suitable panel exists -> raise NotFoundError (do NOT create);
            - set UNDER_REVIEW and persist.
    - otherwise -> 400.
    """
    LOGGER.debug("update_proposal_service prsl_id=%s user_id=%s", prsl_id, user_id)

    # Transform & validate
    try:
        transformed = transform_update_proposal(payload)
        candidate = Proposal.model_validate(transformed)
    except ValidationError as err:
        raise BadRequestError(
            detail=f"Validation error after transforming proposal: {err.args[0]}"
        ) from err

    # Ensure the proposal exists
    existing = uow.prsls.get(prsl_id)
    if not existing:
        raise NotFoundError(detail=f"Proposal not found: {prsl_id}")

    # Permissions
    rows = assert_user_has_permission_for_proposal(
        uow=uow, prsl_id=prsl_id, user_id=user_id
    )

    if candidate.status == ProposalStatus.DRAFT:
        _require_perm(rows, ProposalPermissions.Update, "update", prsl_id, user_id)
        updated = uow.prsls.add(candidate, user_id)
        LOGGER.info("Proposal %s prepared with status=%s", prsl_id, updated.status)
        return updated

    if candidate.status != ProposalStatus.SUBMITTED:
        raise BadRequestError(
            detail="Unsupported status. Only DRAFT or SUBMITTED are allowed."
        )
    _require_perm(rows, ProposalPermissions.Submit, "submit", prsl_id, user_id)

    # ---- Close-date gate (hard-coded) ----
    # Midnight (00:00:00) UTC of the close date
    CLOSE_DATE = date(2025, 12, 31)
    CLOSE_ON = datetime.combine(CLOSE_DATE, time(0, 0, tzinfo=timezone.utc))

    def _as_utc_dt(v) -> datetime:
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, datetime):
            return (
                v.astimezone(timezone.utc)
                if v.tzinfo
                else v.replace(tzinfo=timezone.utc)
            )
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )

    submitted_dt = _as_utc_dt(candidate.submitted_on)

    # If at/after close date: skip any changes
    if submitted_dt >= CLOSE_ON:
        LOGGER.info(
            "Skipping panel assignment & status update for prsl_id=%s: "
            "submitted_on=%s >= CLOSE_ON=%s",
            prsl_id,
            submitted_dt.isoformat(),
            CLOSE_ON.isoformat(),
        )
        return existing

    # ---- assign to existing panel only (no creation) ----
    sv_name = "Science Verification"
    sv = get_latest_entity_by_id(
        uow.panels.query(CustomQuery(name=sv_name)), "panel_id"
    )
    target_name = sv_name if sv else getattr(candidate.info, "science_category", None)

    panel_list = get_latest_entity_by_id(
        uow.panels.query(CustomQuery(name=target_name)), "panel_id"
    )
    panel = panel_list[0] if panel_list else None
    if not panel:
        raise NotFoundError(detail=f"Target panel not found: {target_name}")

    now = datetime.now(timezone.utc)

    def _entry_prsl_id(entry):
        return (
            entry["prsl_id"] if isinstance(entry, dict) else getattr(entry, "prsl_id")
        )

    existing_ids = {_entry_prsl_id(p) for p in (panel.proposals or [])}
    if candidate.prsl_id not in existing_ids:
        assignment = ProposalAssignment(prsl_id=candidate.prsl_id, assigned_on=now)
        panel.proposals.append(assignment)
        uow.panels.add(panel)

    candidate.status = ProposalStatus.UNDER_REVIEW
    updated = uow.prsls.add(candidate, user_id)
    LOGGER.info("Proposal %s prepared with status=%s", prsl_id, updated.status)
    return updated
