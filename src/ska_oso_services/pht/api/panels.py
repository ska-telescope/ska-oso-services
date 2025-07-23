import logging
import uuid
from datetime import datetime, timezone
from typing import Union

from fastapi import APIRouter
from ska_db_oda.persistence.domain.query import CustomQuery, MatchType, UserQuery
from ska_oso_pdm.proposal.proposal import ProposalStatus
from ska_oso_pdm.proposal_management.panel import Panel

from ska_oso_services.common import oda
from ska_oso_services.common.error_handling import (
    BadRequestError,
    UnprocessableEntityError,
)
from ska_oso_services.pht.model import PanelCreateResponse
from ska_oso_services.pht.utils.constants import REVIEWERS
from ska_oso_services.pht.utils.pht_handler import (
    build_panel_response,
    build_sv_panel_proposals,
    get_latest_entity_by_id,
    group_proposals_by_science_category,
)
from ska_oso_services.pht.utils.validation import validate_duplicates

router = APIRouter(prefix="/panels", tags=["PMT API - Panel Management"])

logger = logging.getLogger(__name__)


@router.post(
    "/", summary="Create a panel", response_model=Union[str, list[PanelCreateResponse]]
)
def create_panel(param: Panel) -> Union[str, list[PanelCreateResponse]]:
    """
    Creates panels:
    - If science verification create a single
    'Science Verification' panel with all submitted proposals assigned to it.
    - Else: Create panels for PANEL_NAME_POOL and assigns
    proposals based on science_category type.
    """
    # Get this panel name pool from OSD data when available
    PANEL_NAME_POOL = [
        "Cosmology",
        "Cradle of Life",
        "Epoch of Re-ionization",
        "Extragalactic continuum",
        "Extragalactic Spectral line",
        "Gravitational Waves",
        "High Energy Cosmic Particles",
        "HI Galaxy science",
        "Magnetism",
        "Our Galaxy",
        "Pulsars",
        "Solar, Heliospheric and Ionospheric Physics",
        "Transients",
        "VLBI",
    ]
    with oda.uow() as uow:
        # Fetch proposals (may be empty)
        query_param = CustomQuery(status=ProposalStatus.SUBMITTED)
        proposals = (
            get_latest_entity_by_id(uow.prsls.query(query_param), "prsl_id") or []
        )

        is_sv = "SCIENCE VERIFICATION" in param.name.strip().upper()
        reviewers = param.reviewers or []

        if is_sv:
            # Science Verification panel
            panel = Panel(
                panel_id=f"panel-{str(uuid.uuid4())[:9]}",
                name="Science Verification",
                reviewers=reviewers,
                proposals=build_sv_panel_proposals(proposals),
            )
            created_panel = uow.panels.add(panel)  # pylint: disable=no-member
            uow.commit()
            return created_panel.panel_id

        # science category-type panels (always create all if does not exist)
        grouped = group_proposals_by_science_category(proposals, PANEL_NAME_POOL)
        panel_objs = {}
        for panel_name in PANEL_NAME_POOL:
            proposal_list = grouped.get(panel_name, [])

            existing_panel = get_latest_entity_by_id(
                uow.panels.query(  # pylint: disable=no-member
                    CustomQuery(name=panel_name)
                ),
                "panel_id",
            )
            now = datetime.now(timezone.utc)
            existing_panel = existing_panel[0] if existing_panel else None
            if existing_panel:
                logger.info(
                    "Panel '%s' exists (ID: %s). Adding %d proposals.",
                    panel_name,
                    existing_panel.panel_id,
                    len(proposal_list),
                )
                existing_ids = {
                    proposal["prsl_id"] for proposal in existing_panel.proposals
                }
                for proposal in proposal_list:
                    if proposal.prsl_id not in existing_ids:
                        existing_panel.proposals.append(
                            {"prsl_id": proposal.prsl_id, "assigned_on": now}
                        )
                panel_objs[panel_name] = existing_panel
            else:
                new_panel = Panel(
                    panel_id=f"panel-{str(uuid.uuid4())[:9]}",
                    name=panel_name,
                    reviewers=reviewers,
                    proposals=[
                        {"prsl_id": proposal.prsl_id, "assigned_on": now}
                        for proposal in proposal_list
                    ],
                )
                created_panel = uow.panels.add(new_panel)  # pylint: disable=no-member
                panel_objs[panel_name] = created_panel

        uow.commit()
        return build_panel_response(panel_objs)


@router.put("/{panel_id}", summary="Update a panel")
def update_panel(panel_id: str, param: Panel) -> str:
    logger.debug("POST panel")
    # Ensure ID match
    if param.panel_id != panel_id:
        logger.warning(
            "Proposal ID mismatch: Proposal ID=%s in path, body ID=%s",
            panel_id,
            param.panel_id,
        )
        raise UnprocessableEntityError(
            detail="Proposal ID in path and body do not match."
        )
    reviewer_ids = validate_duplicates(param.reviewers, "reviewer_id")
    for reviewer_id in reviewer_ids:
        if not any([r["id"] == reviewer_id for r in REVIEWERS]):
            raise BadRequestError(f"Reviewer '{reviewer_id}' does not exist")

    validate_duplicates(param.proposals, "prsl_id")
    with oda.uow() as uow:
        panel = uow.panels.add(param)  # pylint: disable=no-member
        uow.commit()
    logger.info("Panel successfully created with ID %s", panel.panel_id)
    return panel.panel_id


@router.get("/{panel_id}", summary="Retrieve an existing panel by panel_id")
def get_panel(panel_id: str) -> Panel:
    logger.debug("GET panel panel_id: %s", panel_id)

    with oda.uow() as uow:
        panel = uow.panels.get(panel_id)  # pylint: disable=no-member
    logger.info("Panel retrieved successfully: %s", panel_id)
    return panel


@router.get(
    "/list/{user_id}", summary="Get all panels matching the given query parameters"
)
def get_panels_for_user(user_id: str) -> list[Panel]:
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
