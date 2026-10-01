"""
These functions map to the API paths, with the returned value being the API response
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter
from pydantic import AwareDatetime
from ska_aaa_authhelpers import AuthContext, Role
from ska_db_oda.common.uow import UnitOfWork
from ska_db_oda.postgres import TABLES
from ska_db_oda.postgres.mapping import INTERNAL_STATUS_TO_PUBLIC_LABEL
from ska_oso_pdm.project import Project
from ska_oso_pdm.proposal.proposal import ProposalStatus
from sqlalchemy import Text, and_, cast, null, select

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.model import AppModel
from ska_oso_services.odt.service.project_generator import generate_project

LOGGER = logging.getLogger(__name__)

API_ROLES = {
    Role.INTERNAL,
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
    prj_status: str | None = None
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

    # Single combined query, executed via uow.execute() as it spans two entity
    # tables that the typed uow.<repo>.filter()/query() methods can't join in one
    # round trip: every Project (LEFT JOIN'd to its current status) UNION ALL'd
    # with every non-draft Proposal that has no linked Project (see SKB-1031 for
    # the draft exclusion).
    projects = TABLES.projects
    proposals = TABLES.proposals
    current_status = TABLES.current_status

    project_status_join = projects.outerjoin(
        current_status,
        and_(
            projects.c.id == current_status.c.entity_id,
            cast(current_status.c.entity_table, Text) == "project.projects",
        ),
    )

    project_rows = select(
        projects.c.id.label("prj_id"),
        projects.c.version.label("prj_version"),
        projects.c.parent_fk.label("prsl_id"),
        null().label("prsl_version"),
        projects.c.data["name"].astext.label("title"),
        current_status.c.status.label("prj_status"),
        projects.c.created_by.label("prj_created_by"),
        projects.c.created_on.label("prj_created_on"),
        projects.c.last_modified_by.label("prj_last_modified_by"),
        projects.c.last_modified_on.label("prj_last_modified_on"),
    ).select_from(project_status_join)

    # As the Project/Proposal relationship is stored as a foreign key on the
    # Project, Proposals without a Project are found via this anti-join.
    proposals_without_project = select(
        null().label("prj_id"),
        null().label("prj_version"),
        proposals.c.id.label("prsl_id"),
        proposals.c.version.label("prsl_version"),
        proposals.c.data["proposal_info"]["title"].astext.label("title"),
        null().label("prj_status"),
        null().label("prj_created_by"),
        null().label("prj_created_on"),
        null().label("prj_last_modified_by"),
        null().label("prj_last_modified_on"),
    ).where(
        proposals.c.status != ProposalStatus.DRAFT.value,
        ~proposals.c.id.in_(select(projects.c.parent_fk).where(projects.c.parent_fk.is_not(None))),
    )

    stmt = project_rows.union_all(proposals_without_project)

    with oda as uow:
        rows = uow.execute(stmt)

    return [_project_proposal_details(row) for row in rows]


def _project_proposal_details(row: dict) -> ProposalProjectDetails:
    """Map a raw row from the prj_details query to the API view model."""
    prj_status = None
    if row["prj_status"] is not None:
        prj_status = INTERNAL_STATUS_TO_PUBLIC_LABEL["project.projects"][row["prj_status"]].value

    return ProposalProjectDetails(
        prj_id=row["prj_id"],
        prj_version=row["prj_version"],
        prsl_id=row["prsl_id"],
        prsl_version=row["prsl_version"],
        title=row["title"],
        prj_status=prj_status,
        prj_created_by=row["prj_created_by"],
        prj_created_on=row["prj_created_on"],
        prj_last_modified_by=row["prj_last_modified_by"],
        prj_last_modified_on=row["prj_last_modified_on"],
    )
