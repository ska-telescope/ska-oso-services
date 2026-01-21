import logging
from typing import Annotated, Union

from fastapi import APIRouter
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.auth_context import AuthContext
from ska_db_oda.persistence.domain.query import CustomQuery
from ska_oso_pdm.proposal.proposal import ProposalStatus
from ska_oso_pdm.proposal_management.panel import Panel

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import UnprocessableEntityError
from ska_oso_services.pht.models.domain import PrslRole
from ska_oso_services.pht.models.schemas import PanelAssignResponse, PanelBatchCreateResult
from ska_oso_services.pht.service.panel_operations import (
    assign_to_existing_panel,
    build_assignment_response,
    build_sv_panel_proposals,
    ensure_decision_exist_or_create,
    ensure_review_exist_or_create,
    ensure_submitted_proposals_under_review,
    group_proposals_by_science_category,
)
from ska_oso_services.pht.utils.constants import PANEL_NAME_POOL, SV_NAME
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
)
def create_panel(
    param: Panel,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> str:
    """This endpoint may not be needed in the future.

    The idea is to auto-generate panels and assign proposals.
    """
    logger.debug("POST panel")

    with oda.uow() as uow:
        panel: Panel = uow.panels.add(param, auth.user_id)  # pylint: disable=no-member
        uow.commit()

    logger.info("Panel successfully created with ID %s", panel.panel_id)
    return panel.panel_id


@router.post(
    "/assignments",
    summary="Assign proposals to panel",
    response_model=Union[str, list[PanelAssignResponse]],
)
def auto_assign_to_panel(
    param: str,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> Union[str, list[PanelAssignResponse]]:
    """
    Auto assign proposals to panels:
    - Check If science verification (SV) exist and assign all submiited proposals.
    - Else: Assign proposals to panels based on the science categories
        (to be pulled in from OSD when available) using the field science
        category in the proposal.
    - Also check that reviews are created for the proposal assigned on this level.
        We need to harmonize some functions here liek the reviews and decison
        creation to a common place,
        given that it is also used the PUT endpoint.
    Note: This endpoint will need to use cycle (Match the cycle in the
        proposal to the panel) here to detrrmine the appropriate panel to
        assign a proposal to. This will soon be a problem after the first
        cycle and when we get to multiple cycles as panels
        can span across cycles.
    """

    with oda.uow() as uow:
        submitted_proposal_refs = (
            get_latest_entity_by_id(
                uow.prsls.query(CustomQuery(status=ProposalStatus.SUBMITTED)), "prsl_id"
            )
            or []
        )
        proposal_ids = [
            proposal if isinstance(proposal, str) else getattr(proposal, "prsl_id")
            for proposal in (submitted_proposal_refs or [])
        ]
        updated_review_ids: list[str] = []
        updated_decison_ids: list[str] = []

        name_raw = (param or "").strip()

        if SV_NAME.casefold() in name_raw.casefold():

            sv_panel_refs = get_latest_entity_by_id(
                uow.panels.query(CustomQuery(name=SV_NAME)), "panel_id"
            )

            if sv_panel_refs:
                sv_panel_id = sv_panel_refs[0].panel_id

                # If no submitted proposals do nothing.

                if not submitted_proposal_refs:
                    return sv_panel_id

                sv_panel = uow.panels.get(sv_panel_id)

                sv_candidate_assignments = build_sv_panel_proposals(submitted_proposal_refs)

                # Append only proposals not already assigned to the SV panel
                existing_prsl_ids = {proposal.prsl_id for proposal in (sv_panel.proposals or [])}
                sv_assignments_to_add = [
                    candidate
                    for candidate in sv_candidate_assignments
                    if candidate.prsl_id not in existing_prsl_ids
                ]
                if sv_assignments_to_add:
                    sv_panel.proposals = (sv_panel.proposals or []) + sv_assignments_to_add

                # TODO: move the reviews and decison creation to a common function
                # to be used here and the PUT endpoint.

                # Panel Decision for every proposal in the panel
                for prsl_id in proposal_ids:
                    pnld_id = ensure_decision_exist_or_create(uow, sv_panel, prsl_id)
                    updated_decison_ids.append(pnld_id)

                # Technical Review for every (technical reviewer × proposal) pair
                if sv_panel.tech_reviewers:
                    for tech in sv_panel.tech_reviewers:
                        tech_reviewer_id = tech.reviewer_id
                        for prsl_id in proposal_ids:
                            rvw_ids = ensure_review_exist_or_create(
                                uow,
                                sv_panel,
                                kind="Technical Review",
                                reviewer_id=tech_reviewer_id,
                                proposal_id=prsl_id,
                            )
                            updated_review_ids.append(rvw_ids)

                # Science Reviews for every (science reviewer × proposal) pair
                if sv_panel.sci_reviewers:
                    for sci in sv_panel.sci_reviewers:
                        sci_reviewer_id = sci.reviewer_id
                        for prsl_id in proposal_ids:
                            rvw_ids = ensure_review_exist_or_create(
                                uow,
                                sv_panel,
                                kind="Science Review",
                                reviewer_id=sci_reviewer_id,
                                proposal_id=prsl_id,
                            )
                            updated_review_ids.append(rvw_ids)

                persisted = uow.panels.add(sv_panel, auth.user_id)

                uow.commit()
                # ---------Set UNDER_REVIEW only for newly added proposals------
                ensure_submitted_proposals_under_review(
                    uow, auth, (a.prsl_id for a in sv_assignments_to_add)
                )
                logger.info(
                    "Updated existing Science Verification panel %s (added %d proposals)",
                    sv_panel_id,
                    len(sv_assignments_to_add),
                )
                return build_assignment_response(
                    {SV_NAME: (persisted, len(sv_assignments_to_add))}
                )

        # ------------------Assignment by Science category panels-------------
        # TODO: In the future, add a check to only allow a proposal to be in one panel
        # Updates needed here: Create reviews and decisions automatically when
        # we move to multiple panels
        proposals_by_category = group_proposals_by_science_category(
            submitted_proposal_refs, PANEL_NAME_POOL
        )

        existing_by_name: dict[str, Panel] = {}
        for pname in PANEL_NAME_POOL:
            refs = get_latest_entity_by_id(uow.panels.query(CustomQuery(name=pname)), "panel_id")
            if refs:
                existing_by_name[pname] = uow.panels.get(refs[0].panel_id)

        updates: dict[str, tuple[Panel, int]] = {}
        skipped_missing: list[str] = []
        ids_for_status: set[str] = set()

        for panel_name, proposals_for_name in proposals_by_category.items():
            panel = existing_by_name.get(panel_name)
            if not panel:
                skipped_missing.append(panel_name)
                continue

            persisted, added_count, added_ids = assign_to_existing_panel(
                uow=uow,
                auth=auth,
                panel=panel,
                proposals=proposals_for_name,
                sci_reviewers=panel.sci_reviewers,
                tech_reviewers=panel.tech_reviewers,
            )
            updates[panel_name] = (persisted, added_count)
            ids_for_status.update(added_ids)

        uow.commit()
        if ids_for_status:
            ensure_submitted_proposals_under_review(uow, auth, ids_for_status)
        if skipped_missing:
            logger.warning(
                "Skipped %d categories with no matching existing panel: %s",
                len(skipped_missing),
                ", ".join(skipped_missing),
            )

        logger.info("Category-based assignments complete (no creation).")
        return build_assignment_response(updates)


@router.post(
    "/generate",
    summary="Create a panel",
    response_model=Union[str, PanelBatchCreateResult],
)
def auto_create_panel(
    param: str,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> Union[str, PanelBatchCreateResult]:
    """
    Creates panels based on the request.

    - If the request refers to the Science Verification panel (SV_NAME),
      return its panel_id.
      If it doesn't exist, create it and return the new panel_id (str).
    - Otherwise, ensure all science-category panels in PANEL_NAME_POOL exist.
      Create any missing ones, and return a summary:
      {created_count, created_names}.

    Auto creates panels:
    - If science verification (SV), create a single panel called
      'Science Verification'.
    - Else: Create panels for PANEL_NAME_POOL, which is the science categories
        (to be pulled in from OSD when available) and return a summary:
        {created_count, created_names}..
    Note: We will need to use cycle (Match the cycle in the
        proposal to the panel) here to detrrmine the appropriate panel to
        assign a proposal to. This will soon be a problem after the first
        cycle and when we get to multiple cycles as panels
        can span across cycles.
    """

    name_raw = (param or "").strip()

    with oda.uow() as uow:
        # --- Science Verification panel path ---
        if SV_NAME.casefold() in name_raw.casefold():
            existing = get_latest_entity_by_id(
                uow.panels.query(CustomQuery(name=SV_NAME)), "panel_id"
            )
            if existing:
                return existing[0].panel_id  # already exists

            sv_panel = Panel(
                panel_id=generate_entity_id("panel"),
                name=SV_NAME,
                cycle="SKAO_2027_1",  # keep if this is a business rule for SV
            )
            created = uow.panels.add(sv_panel, auth.user_id)
            uow.commit()
            logger.info("Science Verification panel created (panel_id=%s)", created.panel_id)
            return created.panel_id

        # --- Science category panels path ---
        created_names: list[str] = []

        for panel_name in PANEL_NAME_POOL:
            existing = get_latest_entity_by_id(
                uow.panels.query(CustomQuery(name=panel_name)), "panel_id"
            )
            panel = existing[0] if existing else None
            if panel:
                continue  # already present

            new_panel = Panel(
                panel_id=generate_entity_id("panel"),
                name=panel_name,
                # add cycle here if non-SV panels also require it:
                # cycle="SKAO_2027_1",
            )
            uow.panels.add(new_panel, auth.user_id)
            created_names.append(panel_name)

        # Commit only if we created something
        if created_names:
            uow.commit()
            logger.info(
                "Panels created: %d (%s)",
                len(created_names),
                ", ".join(created_names),
            )
        else:
            logger.info("No panels created; all already existed.")

        return PanelBatchCreateResult(
            created_count=len(created_names),
            created_names=created_names,
        )


@router.get(
    "/{panel_id}",
    summary="Retrieve an existing panel by panel_id",
    dependencies=[
        Permissions(
            roles=[PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
            scopes=[Scope.PHT_READ],
        )
    ],
)
def get_panel_by_id(panel_id: str) -> Panel:
    logger.debug("GET panel panel_id: %s", panel_id)

    with oda.uow() as uow:
        panel = uow.panels.get(panel_id)
    logger.info("Panel retrieved successfully: %s", panel_id)
    return panel


@router.put(
    "/{panel_id}",
    summary="Update a panel",
)
def update_panel(
    panel_id: str,
    param: Panel,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> Panel:
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
    # This will be situations where the Admin re-assignes proposals due to
    # conflicts or something else.

    with oda.uow() as uow:
        proposal_ids = [
            proposal if isinstance(proposal, str) else getattr(proposal, "prsl_id")
            for proposal in (param.proposals or [])
        ]
        updated_review_ids: list[str] = []
        updated_decison_ids: list[str] = []

        # Panel Decision for every proposal in the panel
        for prsl_id in proposal_ids:
            pnld_id = ensure_decision_exist_or_create(uow, param, prsl_id)
            updated_decison_ids.append(pnld_id)

        # Technical Review for every (technical reviewer × proposal) pair
        if param.tech_reviewers:
            for tech in param.tech_reviewers:
                tech_reviewer_id = tech.reviewer_id
                for prsl_id in proposal_ids:
                    rvw_ids = ensure_review_exist_or_create(
                        uow,
                        param,
                        kind="Technical Review",
                        reviewer_id=tech_reviewer_id,
                        proposal_id=prsl_id,
                    )
                    updated_review_ids.append(rvw_ids)

        # Science Reviews for every (science reviewer × proposal) pair
        if param.sci_reviewers:
            for sci in param.sci_reviewers:
                sci_reviewer_id = sci.reviewer_id
                for prsl_id in proposal_ids:
                    rvw_ids = ensure_review_exist_or_create(
                        uow,
                        param,
                        kind="Science Review",
                        reviewer_id=sci_reviewer_id,
                        proposal_id=prsl_id,
                    )
                    updated_review_ids.append(rvw_ids)
        # TODO: check if proposal is added to another panel
        # A proposal should only be in one panel
        # for prsl_id in proposal_ids:
        #     query_param = CustomQuery(prsl_id=prsl_id)
        #     assigned_proposal =
        # get_latest_entity_by_id(uow.panels.query(query_param), "panel_id")
        #     existing_panel = assigned_proposal[0] if assigned_proposal else None

        #     if existing_panel and existing_panel.panel_id != panel_id:
        #         raise UnprocessableEntityError(
        #             detail=f"Proposal '{prsl_id}' is already
        # assigned to panel '{existing_panel.panel_id}'."
        #         )

        # Persist the panel
        panel = uow.panels.add(param)
        # update proposal status to under review
        ensure_submitted_proposals_under_review(uow, auth, (r for r in proposal_ids))

        uow.commit()
    logger.info("Panel %s updated; reviews updated=%d", panel.panel_id, len(updated_review_ids))
    return panel


@router.get(
    "/",
    summary="Get all panels matching the given query parameters",
    dependencies=[
        Permissions(
            roles=[PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER],
            scopes=[Scope.PHT_READ],
        )
    ],
)
def get_panels() -> list[Panel]:
    """
    Function that requests to GET /panels are mapped to

    Retrieves the Panels for the given cycle ID from the
    underlying data store, if available

    :return: a tuple of a list of Panel
    """
    logger.debug("GET PANEL LIST query")

    with oda.uow() as uow:
        query_param = CustomQuery()
        panels = get_latest_entity_by_id(uow.panels.query(query_param), "panel_id")

        logger.debug("Found %d panels", len(panels))
        return panels
