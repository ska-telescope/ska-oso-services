"""
These functions map to the API paths, with the returned value being the API response
"""

import logging

from fastapi import APIRouter
from ska_aaa_authhelpers import Role
from ska_oso_pdm.project import Project

from ska_oso_services.common import oda
from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.odt.api.prjs import _create_prj_status_entity
from ska_oso_services.odt.service.project_generator import generate_project

LOGGER = logging.getLogger(__name__)

API_ROLES = {
    Role.SW_ENGINEER,
    Role.LOW_TELESCOPE_OPERATOR,
    Role.MID_TELESCOPE_OPERATOR,
    Role.OPERATIONS_SCIENTIST,
}


router = APIRouter(prefix="/prsls")


@router.post(
    "/{prsl_id}/generateProject",
    summary="Create a new Project from the Proposal, creating a Observing Block for "
    "each group of Observation Sets in the Proposal "
    "and copying over the science data",
    dependencies=[Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE})],
)
def prjs_prsl_post(prsl_id: str) -> Project:
    LOGGER.debug("POST PRSLS generateProject from prsl_id: %s", prsl_id)
    with oda.uow() as uow:
        proposal = uow.prsls.get(prsl_id)
        project = generate_project(proposal)

        persisted_project = uow.prjs.add(project)

        prj_status = _create_prj_status_entity(persisted_project)
        uow.prjs_status_history.add(prj_status)

        uow.commit()

    return persisted_project
