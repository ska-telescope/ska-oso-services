"""
These functions map to the API paths, with the returned value being the API response
"""

import logging
from datetime import datetime

from fastapi import APIRouter
from pydantic import AwareDatetime
from ska_aaa_authhelpers import Role
from ska_db_oda.persistence.domain.query import DateQuery
from ska_oso_pdm.project import Project

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.model import AppModel
from ska_oso_services.odt.api.prjs import _create_prj_status_entity
from ska_oso_services.odt.service.project_generator import generate_project

logger = logging.getLogger(__name__)

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
    prj_id: str | None = None
    title: str | None = None
    created_on: AwareDatetime
    created_by: str
    last_updated_on: AwareDatetime
    last_updated_by: str


@router.post(
    "/{prsl_id}/generateProject",
    summary="Create a new Project from the Proposal, creating a Observing Block for "
    "each group of Observation Sets in the Proposal "
    "and copying over the science data",
    dependencies=[Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE})],
)
def prjs_prsl_post(prsl_id: str) -> Project:
    logger.debug("POST PRSLS generateProject from prsl_id: %s", prsl_id)
    with oda.uow() as uow:
        proposal = uow.prsls.get(prsl_id)
        project = generate_project(proposal)

        persisted_project = uow.prjs.add(project)

        prj_status = _create_prj_status_entity(persisted_project)
        uow.prjs_status_history.add(prj_status)

        uow.commit()

    return persisted_project


@router.get(
    "/project-view",
    summary="Returns a view of the Proposal and Project data for display in the UI "
    "table.The list includes details of all Proposals with the linked Project "
    "(if a Project has been generated). It also includes Projects that have "
    "been created without a Proposal.",
    dependencies=[Permissions(roles=API_ROLES, scopes={Scope.ODT_READ})],
)
def prj_details() -> list[ProposalProjectDetails]:
    LOGGER.debug("GET PRSLS Project View from prsl_id")

    # This is a temporary, inefficient implementation that does an outer join in the
    # Python for all the Projects and Proposals.
    # BTN-2812 has been created to provide this functionality in the ODA SQL.
    with oda.uow() as uow:
        # The easiest way to get all the entities from the ODA interface currently
        # is to just query by a date
        date_query = DateQuery(
            query_type=DateQuery.QueryType.CREATED_BETWEEN,
            start=datetime.fromisoformat("1970-01-01T00:00:00.000000+00:00"),
        )

        all_projects = uow.prjs.query(date_query)

        # As we only display the Proposal ID which is already present in the Project,
        # we can handle the Project with and without Proposal cases in the same
        # way here, without having to search through all_proposals for extra fields
        project_details = [
            ProposalProjectDetails(
                prj_id=project.prj_id,
                prsl_id=project.prsl_ref,
                title=project.name,
                created_by=project.metadata.created_by,
                created_on=project.metadata.created_on,
                last_updated_by=project.metadata.last_modified_by,
                last_updated_on=project.metadata.last_modified_on,
            )
            for project in all_projects
        ]

        all_proposals = uow.prsls.query(date_query)
        # As the Project/Proposal relationship is stored as a foreign key
        # on the Project, to find Proposals without Projects we need to filter
        # in this roundabout way
        projects_with_proposals = [
            project for project in all_projects if project.prsl_ref is not None
        ]
        proposal_ids_with_projects = [
            project.prsl_ref for project in projects_with_proposals
        ]
        proposals_without_projects = [
            proposal
            for proposal in all_proposals
            if proposal.prsl_id not in proposal_ids_with_projects
        ]

        proposal_without_project_details = [
            ProposalProjectDetails(
                prsl_id=proposal.prsl_id,
                title=proposal.info.title,
                created_by=proposal.metadata.created_by,
                created_on=proposal.metadata.created_on,
                last_updated_by=proposal.metadata.last_modified_by,
                last_updated_on=proposal.metadata.last_modified_on,
            )
            for proposal in proposals_without_projects
        ]

        return project_details + proposal_without_project_details
