"""
These functions map to the API paths, with the returned value being the API response
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter
from pydantic import AwareDatetime
from ska_aaa_authhelpers import AuthContext, Role
from ska_db_oda.persistence.domain.query import DateQuery
from ska_db_oda.persistence.fastapicontext import UnitOfWork
from ska_oso_pdm.project import Project
from ska_oso_pdm.proposal.proposal import ProposalStatus

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.model import AppModel
from ska_oso_services.odt.api.prjs import _set_prj_status_to_ready
from ska_oso_services.odt.service.project_generator import generate_project

LOGGER = logging.getLogger(__name__)

API_ROLES = {
    Role.SW_ENGINEER,
    Role.LOW_TELESCOPE_OPERATOR,
    Role.MID_TELESCOPE_OPERATOR,
    Role.OPERATIONS_SCIENTIST,
}


router = APIRouter(prefix="/prsls")


class ProposalProjectDetails(AppModel):
    """
    A view of the Proposal + Projects for the UI
    """

    prsl_id: str | None = None
    prsl_version: int | None = None
    prj_id: str | None = None
    prj_version: int | None = None
    title: str | None = None
    prj_created_on: AwareDatetime | None = None
    prj_created_by: str | None = None
    prj_last_modified_on: AwareDatetime | None = None
    prj_last_modified_by: str | None = None


@router.post(
    "/{prsl_id}/generateProject",
    summary="Create a new Project from the Proposal, creating a Observing Block for "
    "each group of Observation Sets in the Proposal "
    "and copying over the science data",
)
def prjs_prsl_post(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    prsl_id: str,
) -> Project:
    LOGGER.debug("POST PRSLS generateProject from prsl_id: %s", prsl_id)
    with oda as uow:
        proposal = uow.prsls.get(prsl_id)
        project = generate_project(proposal)

        persisted_project = uow.prjs.add(project, user=auth.user_id)

        uow.commit()
    _set_prj_status_to_ready(project.prj_id, auth.user_id, oda)

    return persisted_project


@router.get(
    "/project-view",
    summary="Returns a view of the Proposal and Project data for display in the UI "
    "table.The list includes details of all Proposals with the linked Project "
    "(if a Project has been generated). It also includes Projects that have "
    "been created without a Proposal.",
    dependencies=[Permissions(roles=API_ROLES, scopes={Scope.ODT_READ})],
)
def prj_details(
    oda: UnitOfWork,
) -> list[ProposalProjectDetails]:
    LOGGER.debug("GET PRSLS Project View from prsl_id")

    # This is a temporary, inefficient implementation that does an outer join in the
    # Python for all the Projects and Proposals.
    # BTN-2812 has been created to provide this functionality in the ODA SQL.
    with oda as uow:
        # The easiest way to get all the entities from the ODA interface currently
        # is to just query by a date
        date_query = DateQuery(
            query_type=DateQuery.QueryType.CREATED_BETWEEN,
            start=datetime.fromisoformat("1970-01-01T00:00:00.000000+00:00"),
        )

        def get_latest_entities(entity_list, id_field):
            return list(
                {
                    getattr(entity, id_field): entity
                    for entity in sorted(entity_list, key=lambda x: x.metadata.version)
                }.values()
            )

        all_projects = get_latest_entities(uow.prjs.query(date_query), "prj_id")
        # As we only display the Proposal ID which is already present in the Project,
        # we can handle the Project with and without Proposal cases in the same
        # way here, without having to search through all_proposals for extra fields
        project_details = [
            ProposalProjectDetails(
                prj_id=project.prj_id,
                prj_version=project.metadata.version,
                prsl_id=project.prsl_ref,
                title=project.name,
                prj_created_by=project.metadata.created_by,
                prj_created_on=project.metadata.created_on,
                prj_last_modified_by=project.metadata.last_modified_by,
                prj_last_modified_on=project.metadata.last_modified_on,
            )
            for project in all_projects
        ]

        all_proposals = get_latest_entities(uow.prsls.query(date_query), "prsl_id")
        # Filter out any proposals that are in draft (see SKB-1031 for details)
        all_proposals = [prsl for prsl in all_proposals if prsl.status != ProposalStatus.DRAFT]
        # As the Project/Proposal relationship is stored as a foreign key
        # on the Project, to find Proposals without Projects we need to filter
        # in this roundabout way
        projects_with_proposals = [
            project for project in all_projects if project.prsl_ref is not None
        ]
        proposal_ids_with_projects = [project.prsl_ref for project in projects_with_proposals]
        proposals_without_projects = [
            proposal
            for proposal in all_proposals
            if proposal.prsl_id not in proposal_ids_with_projects
        ]

        proposal_without_project_details = [
            ProposalProjectDetails(
                prsl_id=proposal.prsl_id,
                prsl_version=proposal.metadata.version,
                title=proposal.proposal_info.title,
            )
            for proposal in proposals_without_projects
        ]

        return project_details + proposal_without_project_details
