import logging
from typing import Annotated, Union

from fastapi import APIRouter
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.auth_context import AuthContext
from ska_db_oda.persistence.domain.errors import ODANotFound
from ska_db_oda.persistence.domain.query import CustomQuery, MatchType, UserQuery
from ska_oso_pdm import PanelReview
from ska_oso_pdm.proposal import Proposal
from ska_oso_pdm.proposal.proposal import ProposalStatus
from ska_oso_pdm.proposal_management.panel import Panel
from ska_oso_pdm.proposal_management.review import (
    ReviewStatus,
    TechnicalReview,
)
from starlette_context import context

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import (
    BadRequestError,
    UnprocessableEntityError,
)
from ska_oso_services.pht.models.schemas import PanelCreateRequest, PanelCreateResponse
from ska_oso_services.pht.service.panel_operations import (
    build_panel_response,
    build_sv_panel_proposals,
    group_proposals_by_science_category,
    upsert_panel,
)
from ska_oso_services.pht.utils.constants import PANEL_NAME_POOL, REVIEWERS
from ska_oso_services.pht.utils.pht_helper import (
    generate_entity_id,
    get_latest_entity_by_id,
    validate_duplicates,
)

router = APIRouter(prefix="/panels", tags=["PMT API - Panel Management"])

logger = logging.getLogger(__name__)


@router.post(
    "/",
    summary="Create a panel",
    dependencies=[
        Permissions(
            roles=[Role.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
            scopes=[Scope.PHT_READWRITE],
        )
    ],
)
def create_panel(param: Panel) -> str:
    logger.debug("POST panel")

    with oda.uow() as uow:
        reviewer_ids = validate_duplicates(param.reviewers, "reviewer_id")
        for reviewer_id in reviewer_ids:
            if not any([r["id"] == reviewer_id for r in REVIEWERS]):
                raise BadRequestError(f"Reviewer '{reviewer_id}' does not exist")

        proposal_ids = validate_duplicates(param.proposals, "prsl_id")
        for proposal_id in proposal_ids:
            try:
                proposal: Proposal = uow.prsls.get(proposal_id)
                proposal.status = ProposalStatus.UNDER_REVIEW
                # Update proposal status in the ODA
                uow.prsls.add(proposal)
                logger.info(
                    "Proposal status successfully updated with ID %s", proposal.prsl_id
                )
            except ODANotFound:
                raise BadRequestError(f"Proposal '{proposal_id}' does not exist")

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
def auto_create_panel(param: PanelCreateRequest) -> str:
    """
    Auto creates panels:
    - If science verification, create a single
      'Science Verification' panel with all submitted proposals assigned.
    - Else: Create panels for PANEL_NAME_POOL, which is the science catgories
        (to be pulled in from OSD when available) and assign proposals by
        science_category using the field science category in the proposal.
    """
    with oda.uow() as uow:
        proposals = (
            get_latest_entity_by_id(
                uow.prsls.query(CustomQuery(status=ProposalStatus.SUBMITTED)), "prsl_id"
            )
            or []
        )
        reviewers = param.reviewers or []
        is_sv = "SCIENCE VERIFICATION" in param.name.strip().upper()
        if is_sv:
            existing_panel = get_latest_entity_by_id(
                uow.panels.query(CustomQuery(name="Science Verification")), "panel_id"
            )
            if existing_panel:
                return existing_panel.panel_id
            
            panel = Panel(
                panel_id=generate_entity_id("panel"),
                name="Science Verification",
                reviewers=reviewers,
                proposals=build_sv_panel_proposals(proposals),
            )
            created_panel = uow.panels.add(panel)  # pylint: disable=no-member
            uow.commit()
            return created_panel.panel_id

        # Science category panels
        grouped = group_proposals_by_science_category(proposals, PANEL_NAME_POOL)
        panel_objs = {
            panel_name: upsert_panel(
                uow, panel_name, reviewers, grouped.get(panel_name, [])
            )
            for panel_name in PANEL_NAME_POOL
        }

        uow.commit()
        return build_panel_response(panel_objs)


@router.put(
    "/{panel_id}",
    summary="Update a panel",
    dependencies=[
        Permissions(
            roles=[Role.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER], scopes=[Scope.PHT_READ]
        )
    ],
)
def update_panel(panel_id: str, param: Panel) -> str:
    logger.debug("PUT panel")

    # Ensure ID match
    if param.panel_id != panel_id:
        logger.warning(
            "Panel ID mismatch: Panel ID=%s in path, body ID=%s",
            panel_id,
            param.panel_id,
        )
        raise UnprocessableEntityError(detail="Panel ID in path and body do not match.")

    validate_duplicates(param.reviewers, "reviewer_id")

    with oda.uow() as uow:
        if param.tech_reviewers:
            for proposal in param.proposals:
                tec_review = PanelReview(
                    panel_id=param.panel_id,
                    review_id=generate_entity_id("rvs-tec"),
                    reviewer_id=param.tech_reviewers[0]. reviewer_id,
                    cycle=param.cycle,
                    comments=None,
                    src_net=None,
                    submitted_on=None,
                    submitted_by=None,
                    prsl_id=proposal if isinstance(proposal, str) else proposal.prsl_id,
                    status=ReviewStatus.TO_DO,
                    review_type=TechnicalReview(
                        kind="Technical Review",
                        is_feasible="Yes"
                    ),
                )

                uow.rvws.add(tec_review)  # pylint: disable=E0606
        panel = uow.panels.add(param) 
        uow.commit()
    logger.info("Panel successfully created with ID %s", panel.panel_id)
    return panel.panel_id


@router.get(
    "/{panel_id}",
    summary="Retrieve an existing panel by panel_id"
)
def get_panel(panel_id: str, auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER},
            scopes={Scope.PHT_READ},
        ),
    ],) -> Panel:
    logger.debug("GET panel panel_id: %s", panel_id)

    with oda.uow() as uow:
        panel = uow.panels.get(panel_id, auth.user_id)  # pylint: disable=no-member
    logger.info("Panel retrieved successfully: %s", panel_id)
    return panel


@router.get(
    "/list/{user_id}",
    summary="Get all panels matching the given query parameters",
    dependencies=[
        Permissions(
            roles=[Role.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER], scopes=[Scope.PHT_READ]
        )
    ],
)
def get_panels_for_user(user_id: str, ) -> list[Panel]:
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
