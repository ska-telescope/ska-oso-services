import logging
from typing import Annotated, Union

from fastapi import APIRouter
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.auth_context import AuthContext
from ska_db_oda.repository.domain import CustomQuery
from ska_oso_pdm.proposal.proposal import ProposalStatus
from ska_oso_pdm.proposal_management.panel import Panel

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.error_handling import UnprocessableEntityError
from ska_oso_services.pht.models.domain import PrslRole
from ska_oso_services.pht.models.schemas import PanelAssignResponse, PanelBatchCreateResult
from ska_oso_services.pht.service.panel_operations import (
    _to_prsl_id,
    assign_to_existing_panel,
    build_assignment_response,
    build_sv_panel_proposals,
    ensure_decision_exist_or_create,
    ensure_review_exist_or_create,
    ensure_submitted_proposals_under_review,
    group_proposals_by_science_category,
    set_removed_proposals_to_submitted,
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
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={PrslRole.OPS_PROPOSAL_ADMIN, Role.SW_ENGINEER},
            scopes={Scope.PHT_READWRITE},
        ),
    ],
) -> Union[str, PanelBatchCreateResult]:
    """
    Creates a list of panels for both Science Verification and Science Categories.

    - Ensure 1 Science Verification panel exists; if not, create it.
    - Ensure all science-category panels in PANEL_NAME_POOL exist.
      Create any missing ones,
    - Returns a summary of all newly created panels: {created_count, created_names}.

    Auto creates panels:
    - Create a single panel called 'Science Verification'.
    - Create panels for PANEL_NAME_POOL, which is the science categories
        (to be pulled in from OSD when available)
    - Then return a summary:
        {created_count, created_names}..
    Note: We will need to use cycle (Match the cycle in the
        proposal to the panel) here to detrrmine the appropriate panel to
        assign a proposal to. This will soon be a problem after the first
        cycle and when we get to multiple cycles as panels
        can span across cycles.
    """

    with oda.uow() as uow:

        created_names: list[str] = []

        # --- Science Verification panel ---
        # check if SV panel exist, create if not
        existing = get_latest_entity_by_id(uow.panels.query(CustomQuery(name=SV_NAME)), "panel_id")
        if not existing:
            sv_panel = Panel(
                panel_id=generate_entity_id("panel"),
                name=SV_NAME,
                cycle="SKAO_2027_1",  # keep if this is a business rule for SV
            )
            created = uow.panels.add(sv_panel, auth.user_id)
            uow.commit()
            logger.info("Science Verification panel created (panel_id=%s)", created.panel_id)
            created_names.append(SV_NAME)

        # --- Science category panels ---
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

        # return the combined list of created panel names and count
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
    Updates a panel and ensures:
    - A proposal that already belongs to a different panel is prevented from being assigned
    - Removed proposals are set back to SUBMITTED (if not in an other panel)
    - Newly added proposals are set to UNDER REVIEW
    - Reviews/Decisions exist for all proposals in the panel (create if doesn't exist)
    (Assumption: Only one technical reviewer for a panel for now. Hence,
    only one technical review for each proposal in a panel is needed.)

    """
    logger.debug("PUT panel")
    # ------------------------------------------------------------
    # 1. Validate panel ID consistency
    # ------------------------------------------------------------
    if param.panel_id != panel_id:
        raise UnprocessableEntityError(detail="Panel ID in path and body do not match.")

    validate_duplicates(param.sci_reviewers, "reviewer_id")

    with oda.uow() as uow:

        # --------------------------------------------------------
        # 2. Determine previous vs. new proposals
        # --------------------------------------------------------
        persisted_panel = uow.panels.get(panel_id)

        previous_proposal_ids: set[str] = {
            pid for pid in (_to_prsl_id(x) for x in (persisted_panel.proposals or [])) if pid
        }

        new_proposal_ids: set[str] = {
            pid for pid in (_to_prsl_id(x) for x in (param.proposals or [])) if pid
        }

        removed: set[str] = previous_proposal_ids - new_proposal_ids

        logger.debug(
            "Panel update: previous=%s new=%s removed=%s",
            previous_proposal_ids,
            new_proposal_ids,
            removed,
        )

        # --------------------------------------------------------
        # 3. Load all panels once
        # --------------------------------------------------------
        all_panels = list(uow.panels.query(CustomQuery()))

        # --------------------------------------------------------
        # 4. VALIDATION — ensure newly added proposals are not in
        #    another panel
        # --------------------------------------------------------
        for prsl_id in new_proposal_ids:

            if prsl_id in previous_proposal_ids:
                continue  # already in this panel, skip

            for p in all_panels:
                if not p.proposals:
                    continue

                existing_ids = {pid for pid in (_to_prsl_id(x) for x in p.proposals) if pid}

                if prsl_id in existing_ids and p.panel_id != panel_id:
                    raise UnprocessableEntityError(
                        detail=(
                            f"Submission '{prsl_id}' is already assigned to "
                            f"panel '{p.panel_id}'. A submission can only "
                            f"belong to one panel."
                        )
                    )

        # --------------------------------------------------------
        # 5. REMOVED PROPOSAL PROTECTION
        #    Only revert removed proposals to SUBMITTED if they are
        #    NOT in any other panel.
        # --------------------------------------------------------
        safe_removed = set()

        for prsl_id in removed:
            still_in_other_panel = False

            for p in all_panels:
                if not p.proposals:
                    continue

                existing_ids = {pid for pid in (_to_prsl_id(x) for x in p.proposals) if pid}

                if prsl_id in existing_ids and p.panel_id != panel_id:
                    still_in_other_panel = True
                    break

            if still_in_other_panel:
                logger.debug(
                    "Skipping revert of proposal %s → submitted; still assigned to panel %s",
                    prsl_id,
                    p.panel_id,
                )
            else:
                safe_removed.add(prsl_id)

        # Only revert SAFE removals
        if safe_removed:
            set_removed_proposals_to_submitted(uow, auth, safe_removed)

        # --------------------------------------------------------
        # 6. Persist the updated panel
        # --------------------------------------------------------
        panel = uow.panels.add(param)

        updated_review_ids: list[str] = []
        updated_decision_ids: list[str] = []

        # --------------------------------------------------------
        # 7. Ensure decisions for newly added proposals
        # --------------------------------------------------------
        for prsl_id in new_proposal_ids:
            pnld_id = ensure_decision_exist_or_create(uow, param, prsl_id)
            updated_decision_ids.append(pnld_id)

        # --------------------------------------------------------
        # 8. Ensure Technical reviews
        # --------------------------------------------------------
        if param.tech_reviewers:
            for tech in param.tech_reviewers:
                for prsl_id in new_proposal_ids:
                    rid = ensure_review_exist_or_create(
                        uow,
                        param,
                        kind="Technical Review",
                        reviewer_id=tech.reviewer_id,
                        proposal_id=prsl_id,
                    )
                    updated_review_ids.append(rid)

        # --------------------------------------------------------
        # 9. Ensure Science reviews
        # --------------------------------------------------------
        if param.sci_reviewers:
            for sci in param.sci_reviewers:
                for prsl_id in new_proposal_ids:
                    rid = ensure_review_exist_or_create(
                        uow,
                        param,
                        kind="Science Review",
                        reviewer_id=sci.reviewer_id,
                        proposal_id=prsl_id,
                    )
                    updated_review_ids.append(rid)

        # --------------------------------------------------------
        # 10. Mark new proposals as UNDER REVIEW
        # --------------------------------------------------------
        if new_proposal_ids:
            ensure_submitted_proposals_under_review(
                uow,
                auth,
                (p for p in new_proposal_ids),
            )

        # --------------------------------------------------------
        # 11. Commit
        # --------------------------------------------------------
        uow.commit()

    logger.info(
        "Panel %s updated; reviews updated=%d decisions updated=%d",
        panel.panel_id,
        len(updated_review_ids),
        len(updated_decision_ids),
    )

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
