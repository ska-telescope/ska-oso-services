import logging
from typing import Union

from fastapi import APIRouter
from ska_aaa_authhelpers import Role
from ska_db_oda.persistence.domain.query import CustomQuery, MatchType, UserQuery
from ska_oso_pdm import PanelReview
from ska_oso_pdm.proposal.proposal import ProposalStatus
from ska_oso_pdm.proposal_management.panel import Panel
from ska_oso_pdm.proposal_management.review import ReviewStatus, TechnicalReview

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import UnprocessableEntityError
from ska_oso_services.pht.models.schemas import PanelCreateRequest, PanelCreateResponse
from ska_oso_services.pht.service.panel_operations import (
    build_panel_response,
    build_sv_panel_proposals,
    ensure_review_exist_or_create,
    ensure_submitted_proposals_under_review,
    group_proposals_by_science_category,
    upsert_panel,
)
from ska_oso_services.pht.utils.constants import PANEL_NAME_POOL
from ska_oso_services.pht.utils.pht_helper import (
    generate_entity_id,
    get_latest_entity_by_id,
    validate_duplicates,
)

router = APIRouter(prefix="/panels", tags=["PMT API - Panel Management"])

logger = logging.getLogger(__name__)


@router.post(
    "/create",
    summary="Create a panel",
    dependencies=[
        Permissions(
            roles=[Role.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
            scopes=[Scope.PHT_READWRITE],
        )
    ],
)
def create_panel(param: Panel) -> str:
    """This endpoint may not be needed in the future.

    The idea is to auto-generate panels and assign proposals.
    """
    logger.debug("POST panel")

    with oda.uow() as uow:
        panel: Panel = uow.panels.add(param)  # pylint: disable=no-member
        uow.commit()

    logger.info("Panel successfully created with ID %s", panel.panel_id)
    return panel.panel_id


@router.post(
    "/auto-create",
    summary="Create a panel",
    response_model=Union[str, list[PanelCreateResponse]],
    dependencies=[
        Permissions(
            roles=[Role.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER], scopes=[Scope.PHT_READ]
        )
    ],
)
def auto_create_panel(request: PanelCreateRequest) -> str | list[PanelCreateResponse]:
    """
    Auto creates panels:
    - If science verification, create a single panel called
      'Science Verification' with all submitted proposals assigned.
    - Else: Create panels for PANEL_NAME_POOL, which is the science categories
        (to be pulled in from OSD when available) and assign proposals by
        science_category using the field science category in the proposal.
    """
    with oda.uow() as uow:
        submitted_proposals = (
            get_latest_entity_by_id(
                uow.prsls.query(CustomQuery(status=ProposalStatus.SUBMITTED)), "prsl_id"
            )
            or []
        )

        science_reviewers = request.sci_reviewers or []
        technical_reviewers = request.tech_reviewers or []

        is_science_verification = "SCIENCE VERIFICATION" in request.name.strip().upper()
        if is_science_verification:
            existing_sv_panels = get_latest_entity_by_id(
                uow.panels.query(CustomQuery(name="Science Verification")), "panel_id"
            )
            if existing_sv_panels:
                ensure_submitted_proposals_under_review(uow, submitted_proposals)
                return existing_sv_panels[0].panel_id

            sv_assignments = build_sv_panel_proposals(submitted_proposals)

            new_panel = Panel(
                panel_id=generate_entity_id("panel"),
                name="Science Verification",
                sci_reviewers=science_reviewers,
                tech_reviewers=technical_reviewers,
                proposals=sv_assignments,
            )
            created_panel = uow.panels.add(new_panel)

            # Update each referenced proposal to UNDER_REVIEW
            ensure_submitted_proposals_under_review(uow, submitted_proposals)
            uow.commit()
            logger.info("Science Verification panel successfully updated")
            return created_panel.panel_id

        # Science category panels
        proposals_by_category = group_proposals_by_science_category(
            submitted_proposals, PANEL_NAME_POOL
        )

        panels_by_name = {
            panel_name: upsert_panel(
                uow=uow,
                panel_name=panel_name,
                science_reviewers=science_reviewers,
                technical_reviewers=technical_reviewers,
                proposals=proposals_by_category.get(panel_name, []),
            )
            for panel_name in PANEL_NAME_POOL
        }
        ensure_submitted_proposals_under_review(uow, submitted_proposals)

        uow.commit()
        logger.info("Panels successfully updated")
        return build_panel_response(panels_by_name)


@router.get(
    "/{panel_id}",
    summary="Retrieve an existing panel by panel_id",
    dependencies=[
        Permissions(
            roles=[Role.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER], scopes=[Scope.PHT_READ]
        )
    ],
)
def get_panel_by_id(panel_id: str) -> Panel:
    logger.debug("GET panel panel_id: %s", panel_id)

    with oda.uow() as uow:
        panel = uow.panels.get(panel_id)  # pylint: disable=no-member
    logger.info("Panel retrieved successfully: %s", panel_id)
    return panel


@router.put(
    "/{panel_id}",
    summary="Update a panel",
    dependencies=[
        Permissions(
            roles=[Role.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
            scopes=[Scope.PHT_READWRITE],
        )
    ],
)
def update_panel(panel_id: str, param: Panel) -> str:
    """
    Takes the incoming panel payload and creates the technical review.

    Assumption: Only one technical reviewer for a panel for now. Hence,
    only one technical review for each proposal in a panel is needed.
    Note: In the future, if needed, check for new proposals added to the panel
    and handle the status accordingly. This could be due to conflicts and
    proposals being moved around.
    """
    logger.debug("PUT panel")

    # Ensure ID match
    if param.panel_id != panel_id:
        logger.warning(
            "Panel ID mismatch: Panel ID=%s in path, body ID=%s",
            panel_id,
            param.panel_id,
        )
        raise UnprocessableEntityError(detail="Panel ID in path and body do not match.")

    validate_duplicates(param.sci_reviewers, "reviewer_id")
    # TODO: check for any new proposal added and handle status appropriately here
    # This will be situations where the Admin re-assignes proposals


    with oda.uow() as uow:
        proposal_ids = [
            p if isinstance(p, str) else getattr(p, "prsl_id")
            for p in (param.proposals or [])
        ]

        # Technical Review (only one technical reviewer is expected for now)
        if param.tech_reviewers:
            tech_reviewer_id = param.tech_reviewers[0].reviewer_id
            for prsl_id in proposal_ids:
                ensure_review_exist_or_create(uow, param, kind="Technical Review", reviewer_id=tech_reviewer_id, proposal_id=prsl_id)

        # Science Reviews for every (science reviewer × proposal) pair
        if param.sci_reviewers:
            for sci in param.sci_reviewers:
                sci_reviewer_id = sci.reviewer_id
                for prsl_id in proposal_ids:
                    ensure_review_exist_or_create(uow, param, kind="Science Review", reviewer_id=sci_reviewer_id, proposal_id=prsl_id)

        # Persist the panel itself
        panel = uow.panels.add(param)
        uow.commit()
    logger.info("Panel successfully updated with ID %s", panel.panel_id)
    return panel.panel_id



@router.get(
    "/users/{user_id}/panels",
    summary="Get all panels matching the given query parameters",
    dependencies=[
        Permissions(
            roles=[Role.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER], scopes=[Scope.PHT_READ]
        )
    ],
)
def get_panels_for_user(
    user_id: str,
) -> list[Panel]:
    """
    Function that requests to GET /panels are mapped to

    Retrieves the Panels for the given user ID from the
    underlying data store, if available

    :param user_id: identifier of the Panel
    :return: a tuple of a list of Panel
    """
    # TODO: Agree on path name and fix list in path - also in proposals  Tonye
    logger.debug("GET PANEL LIST query for the user: %s", user_id)

    with oda.uow() as uow:
        query_param = UserQuery(user=user_id, match_type=MatchType.EQUALS)
        panels = uow.panels.query(query_param)  # pylint: disable=no-member

        logger.debug("Found %d panels for user: %s", len(panels), user_id)
        return panels
