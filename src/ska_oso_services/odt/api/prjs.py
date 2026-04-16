"""
These functions map to the API paths, with the returned value being the API response
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Optional

from astropy.time import Time
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ska_aaa_authhelpers import AuthContext, Role
from ska_db_oda.repository.status import Status
from ska_db_oda.rest.fastapicontext import UnitOfWork
from ska_oso_pdm import ICRSCoordinates, SubArrayLOW, Target, TelescopeType
from ska_oso_pdm.builders.utils import target_id
from ska_oso_pdm.project import Author, ObservingBlock, Project
from ska_oso_pdm.sb_definition import SBDefinition
from ska_ser_skuid import EntityType, mint_skuid

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.coordinateslookup import get_coordinates
from ska_oso_services.common.error_handling import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
)
from ska_oso_services.common.osdmapper import get_subarray_specific_parameter_from_osd
from ska_oso_services.odt.service.calibrator_sweep_sbd_generator import generate_cal_sweep_sbd
from ska_oso_services.odt.service.frequency_sweep_calibrator import generate_frequency_sweep
from ska_oso_services.odt.service.sbd_generator import generate_sbds

LOGGER = logging.getLogger(__name__)


DEFAULT_AUTHOR = Author(pis=[], cois=[])


DEFAULT_SB_DEFINITION = SBDefinition(
    telescope=TelescopeType.SKA_MID,
    interface="https://schema.skao.int/ska-oso-pdm-sbd/0.1",
)

API_ROLES = {
    Role.SW_ENGINEER,
    Role.LOW_TELESCOPE_OPERATOR,
    Role.MID_TELESCOPE_OPERATOR,
    Role.OPERATIONS_SCIENTIST,
}

router = APIRouter(prefix="/prjs")


def empty_observing_block() -> ObservingBlock:
    return ObservingBlock(obs_block_id=mint_skuid(EntityType.OB), sbd_ids=[])


def _validate_project_has_scheduling_blocks(project: Project) -> None:
    """
    Validates that a project has at least one scheduling block (SBDefinition).

    Args:
        project: The Project to validate

    Raises:
        BadRequestError: If the project has no scheduling blocks
    """
    has_scheduling_blocks = any(bool(ob.sbd_ids) for ob in project.obs_blocks)

    if not has_scheduling_blocks:
        raise BadRequestError(
            detail=(
                f"Cannot set status for '{project.prj_id}' because it has no "
                "scheduling blocks. At least one ObservingBlock must have "
                "associated SBDefinitions."
            )
        )


class CommissioningObservingMode(str, Enum):
    VIS = "VIS"
    PST = "PST"


class CalibratorSweepInputs(BaseModel):
    """Input parameters for calibrator sweep SBDefinition generation."""

    obs_start: datetime
    duration_min: float
    primary_dwell_min: float = 5
    secondary_dwell_min: float | None = 5
    interleave_primary: bool = Field(
        default=False,
        description=(
            "If true, adds a scan on the primary target after every secondary target scan."
        ),
    )
    coarse_channel_start: int = 206
    coarse_channel_bandwidth: int = 96
    mode: CommissioningObservingMode = Field(
        default=CommissioningObservingMode.VIS,
        description="Should be 'VIS' or 'PST', to indicate whether a PST beam "
        "should be added to the observation "
        "(and which catalogue to pick targets from).",
    )
    stations: list[int] = Field(
        default_factory=lambda: get_subarray_specific_parameter_from_osd(
            TelescopeType.SKA_LOW, SubArrayLOW.AA1_ALL, "receptors"
        ),
        description="List of station IDs to set in the SBDefinition. "
        "Will default to the AA1 stations if not given.",
    )


class FrequencySweepInputs(BaseModel):
    """Input parameters for frequency sweep SBDefinition generation."""

    target_name: str | None = Field(
        default=None,
        description="Target name to query the catalogue for. "
        "This will take precedent over ra_str and dec_str",
    )
    ra_str: str | None = Field(
        default=None,
        description="Right ascension of the target if not using the "
        "target_name for a catalogue lookup",
    )
    dec_str: str | None = Field(
        default=None,
        description="Declination of the target if not using the target_name "
        "for a catalogue lookup",
    )
    target_dwell_min: float = 5
    coarse_channel_start: int = 64
    coarse_channel_end: int = 448
    coarse_channel_bandwidth: int = 96
    mode: CommissioningObservingMode = Field(
        default=CommissioningObservingMode.VIS,
        description="Should be 'VIS' or 'PST', to indicate whether a "
        "PST beam should be added to the observation",
    )
    stations: list[int] = Field(
        default_factory=lambda: get_subarray_specific_parameter_from_osd(
            TelescopeType.SKA_LOW, SubArrayLOW.AA1_ALL, "receptors"
        ),
        description="List of station IDs to set in the SBDefinition. "
        "Will default to the AA1 stations if not given.",
    )


def _resolve_frequency_sweep_target(inputs: FrequencySweepInputs) -> Target:
    """Resolve the target for frequency-sweep generation from API inputs."""
    if inputs.target_name:
        target = get_coordinates(inputs.target_name)
        target.target_id = target_id()
        return target

    if inputs.ra_str is not None and inputs.dec_str is not None:
        return Target(
            target_id=target_id(),
            name=inputs.target_name or "frequency-sweep-target",
            reference_coordinate=ICRSCoordinates(
                ra_str=inputs.ra_str,
                dec_str=inputs.dec_str,
            ),
        )

    raise BadRequestError(
        detail=(
            "Provide either target_name for catalog lookup, or both ra_str "
            "and dec_str for manual target coordinates."
        )
    )


@router.get(
    "/{identifier}",
    summary="Get Project by identifier",
    dependencies=[Permissions(roles=API_ROLES, scopes={Scope.ODT_READ, Scope.ODT_READWRITE})],
)
def prjs_get(identifier: str, oda: UnitOfWork) -> Project:
    """
    Retrieves the Project with the given identifier from the underlying
    data store, if available
    """
    LOGGER.debug("GET PRJS prj_id: %s", identifier)
    with oda as uow:
        return uow.prjs.get(identifier)


@router.get(
    "/{identifier}/status",
    summary="Get Project status by identifier",
    dependencies=[Permissions(roles=API_ROLES, scopes={Scope.ODT_READ, Scope.ODT_READWRITE})],
)
def prjs_status_get(identifier: str, oda: UnitOfWork) -> Status:
    """
    Retrieves the current Status of the Project with the given identifier
    from the underlying data store, if available.
    """
    LOGGER.debug("GET PRJS status prj_id: %s", identifier)
    with oda as uow:
        return uow.status.get_current_status(entity_id=identifier)


@router.post("/", summary="Create a new Project")
def prjs_post(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    prj: Optional[Project] = None,
) -> Project:
    """
    Creates a new Project in the underlying data store. The response
    contains the entity as it exists in the data store, with
    a prj_id and metadata populated.
    """
    LOGGER.debug("POST PRJ")
    if prj is None:
        prj = Project(
            obs_blocks=[empty_observing_block()],
            author=DEFAULT_AUTHOR.model_copy(deep=True),
        )
    else:
        if not prj.obs_blocks:
            prj.obs_blocks = [empty_observing_block()]
        if prj.author is None:
            prj.author = DEFAULT_AUTHOR.model_copy(deep=True)
    # Ensure the identifier is None so the ODA doesn't try to perform an update
    if prj.prj_id is not None:
        raise BadRequestError(
            detail=(
                "prj_id given in the body of the POST request. Identifier"
                " generation for new entities is the responsibility of the ODA,"
                " which will fetch them from SKUID, so they should not be given in"
                " this request."
            ),
        )

    with oda as uow:
        updated_prj = uow.prjs.add(prj, user=auth.user_id)
        uow.commit()
    return updated_prj


@router.put("/{identifier}", summary="Update a Project by identifier")
def prjs_put(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    prj: Project,
    identifier: str,
    oda: UnitOfWork,
) -> Project:
    """
    Updates the Project with the given identifier in the underlying
    data store to create a new version.
    """
    LOGGER.debug("PUT PRJS prj_id: %s", identifier)

    if prj.prj_id != identifier:
        raise UnprocessableEntityError(
            detail=(
                "There is a mismatch between the prj_id in the path for "
                "the endpoint and in the JSON payload"
            ),
        )

    with oda as uow:
        # This get will check if the identifier already exists
        # and throw an error if it doesn't
        uow.prjs.get(identifier)
        updated_prj = uow.prjs.add(prj, user=auth.user_id)

        uow.commit()

    return updated_prj


class PrjSBDLinkResponse(BaseModel):
    sbd: SBDefinition
    prj: Project


@router.post(
    "/{identifier}/{obs_block_id}/sbds",
    summary="Create a new SBDefinition linked to a project",
)
def prjs_sbds_post(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    identifier: str,
    obs_block_id: str,
    sbd: Optional[SBDefinition] = None,
) -> PrjSBDLinkResponse:
    """
    Creates an SBDefintiion linked to the given project.
    The response contains the entity as it exists in the data store,
    with an sbd_id and metadata populated.

    If no request body is passed, a default 'empty' SBDefinition will be created.
    """
    if sbd is not None and sbd.ob_ref is not None and sbd.ob_ref != obs_block_id:
        raise BadRequestError(detail="ob_ref in SBDefinition body does not match the request URL")
    with oda as uow:
        prj = uow.prjs.get(identifier)
        if obs_block_id not in [ob.obs_block_id for ob in prj.obs_blocks]:
            raise NotFoundError(detail=f"Observing Block '{obs_block_id}' not found in Project")

        sbd_to_save = sbd if sbd is not None else DEFAULT_SB_DEFINITION.model_copy(deep=True)
        sbd_to_save.ob_ref = obs_block_id
        sbd = uow.sbds.add(sbd_to_save, user=auth.user_id)
        uow.commit()

        # Get the project again to resolve the new child updates
        prj = uow.prjs.get(prj.prj_id)

    return {"sbd": sbd, "prj": prj}


@router.delete(
    "/{identifier}/{obs_block_id}",
    summary="Delete an ObservingBlock from a Project",
    dependencies=[Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE})],
)
def prjs_delete_observing_block(
    oda: UnitOfWork,
    identifier: str,
    obs_block_id: str,
) -> Project:
    """
    Deletes the specified ObservingBlock from the Project, raising an error
    if the ObservingBlock does not exist in the Project. Returns the updated Project.
    """
    LOGGER.debug(
        "DELETE PRJS prj_id: %s, obs_block_id: %s",
        identifier,
        obs_block_id,
    )
    with oda as uow:
        uow.prjs.delete_observing_block(identifier, obs_block_id)
        uow.commit()
    # Return the updated Project
    with oda as uow:
        return uow.prjs.get(identifier)


@router.post(
    "/{identifier}/{obs_block_id}/generateSBDefinitions",
    summary="Generate SBDefinitions for an ObservingBlock within a Project",
    description="Generates SBDefinitions using the ScienceProgramme data in the "
    "ObservingBlock, persists those SBDefinitions in the ODA, adds a "
    "link to the SBDefinitions to the ObservingBlock then persists"
    "the updated Project/ObservingBlock",
)
def prjs_ob_generate_sbds(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    identifier: str,
    obs_block_id: str,
) -> Project:
    LOGGER.debug(
        "POST PRJS generate SBDefinitions for prj_id: %s and obs_block_id: %s",
        identifier,
        obs_block_id,
    )
    updated_sbd_ids = []
    with oda as uow:
        prj = uow.prjs.get(identifier)
        try:
            obs_block = next(
                obs_block for obs_block in prj.obs_blocks if obs_block.obs_block_id == obs_block_id
            )
        except StopIteration:
            # pylint: disable=raise-missing-from
            raise NotFoundError(detail=f"Observing Block '{obs_block_id}' not found in Project")

        sbds = generate_sbds(obs_block)

        for sbd in sbds:
            updated_sbd = uow.sbds.add(sbd, user=auth.user_id)
            updated_sbd_ids.append(updated_sbd.sbd_id)

        updated_prj = uow.prjs.get(prj.prj_id)
        uow.commit()

    return updated_prj


@router.post(
    "/{identifier}/{obs_block_id}/generateCalibratorSweepSBDefinition",
    summary="Generate a calibrator sweep SBDefinition for an ObservingBlock",
    description=(
        "Generates a single SBDefinition for the Low Commissioning calibrator "
        "sweep use case. The generated SBDefinition is persisted in the ODA "
        "and linked to the specified ObservingBlock within the Project."
    ),
)
def prjs_ob_generate_sbds_cal_sweep(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    identifier: str,
    obs_block_id: str,
    inputs: CalibratorSweepInputs,
) -> Project:
    """
    Generate a calibrator sweep SBDefinition and store it in the given
    ObservingBlock within a Project.
    """
    LOGGER.debug(
        "POST PRJS generate Calibrator Sweep SBDefinition for prj_id: %s and obs_block_id: %s",
        identifier,
        obs_block_id,
    )
    updated_sbd_ids = []
    with oda as uow:
        prj = uow.prjs.get(identifier)
        try:
            obs_block = next(
                obs_block for obs_block in prj.obs_blocks if obs_block.obs_block_id == obs_block_id
            )
        except StopIteration:
            # pylint: disable=raise-missing-from
            raise NotFoundError(detail=f"Observing Block '{obs_block_id}' not found in Project")

        sbd = generate_cal_sweep_sbd(
            obs_start=Time(inputs.obs_start),
            duration=timedelta(minutes=inputs.duration_min),
            primary_dwell=timedelta(minutes=inputs.primary_dwell_min),
            secondary_dwell=timedelta(minutes=inputs.secondary_dwell_min),
            interleave_primary=inputs.interleave_primary,
            coarse_channel_start=inputs.coarse_channel_start,
            coarse_channel_bandwidth=inputs.coarse_channel_bandwidth,
            pst_mode=inputs.mode == CommissioningObservingMode.PST,
            stations=inputs.stations,
        )

        sbd.ob_ref = obs_block.obs_block_id

        updated_sbd = uow.sbds.add(sbd, user=auth.user_id)
        updated_sbd_ids.append(updated_sbd.sbd_id)

        updated_prj = uow.prjs.get(prj.prj_id)
        uow.commit()

    return updated_prj


@router.post(
    "/{identifier}/{obs_block_id}/generateFrequencySweepSBDefinition",
    summary="Generate a frequency sweep SBDefinition for an ObservingBlock",
    description=(
        "Generates a single SBDefinition for the Low Commissioning frequency "
        "sweep use case. The generated SBDefinition is persisted in the ODA "
        "and linked to the specified ObservingBlock within the Project."
    ),
)
def prjs_ob_generate_sbds_frequency_sweep(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    identifier: str,
    obs_block_id: str,
    inputs: FrequencySweepInputs,
) -> Project:
    """
    Generate a frequency sweep SBDefinition and store it in the given
    ObservingBlock within a Project.
    """
    LOGGER.debug(
        "POST PRJS generate Frequency Sweep SBDefinition for prj_id: %s and obs_block_id: %s",
        identifier,
        obs_block_id,
    )
    with oda as uow:
        prj = uow.prjs.get(identifier)
        try:
            obs_block = next(
                obs_block for obs_block in prj.obs_blocks if obs_block.obs_block_id == obs_block_id
            )
        except StopIteration:
            # pylint: disable=raise-missing-from
            raise NotFoundError(detail=f"Observing Block '{obs_block_id}' not found in Project")

        target = _resolve_frequency_sweep_target(inputs)

        sbd = generate_frequency_sweep(
            target=target,
            target_dwell=timedelta(minutes=inputs.target_dwell_min),
            coarse_channel_start=inputs.coarse_channel_start,
            coarse_channel_end=inputs.coarse_channel_end,
            coarse_channel_bandwidth=inputs.coarse_channel_bandwidth,
            pst_mode=inputs.mode == CommissioningObservingMode.PST,
            stations=inputs.stations,
        )

        sbd.ob_ref = obs_block.obs_block_id
        uow.sbds.add(sbd, user=auth.user_id)

        updated_prj = uow.prjs.get(prj.prj_id)
        uow.commit()

    return updated_prj


@router.post(
    "/{identifier}/generateSBDefinitions",
    summary="Generate SBDefinitions for all ObservingBlocks within a Project",
    description="Generates SBDefinitions for each ObservingBlock in the Project, "
    "persists those SBDefinitions in the ODA, adds a link to the "
    "SBDefinitions to the ObservingBlock then persists the updated "
    "Project/ObservingBlock",
)
def prjs_generate_sbds(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    oda: UnitOfWork,
    identifier: str,
) -> Project:
    LOGGER.debug("POST PRJS generate SBDefinitions for prj_id: %s", identifier)
    with oda as uow:
        prj = uow.prjs.get(identifier)
        for obs_block in prj.obs_blocks:
            sbds = generate_sbds(obs_block)

            for sbd in sbds:
                uow.sbds.add(sbd, user=auth.user_id)

        updated_prj = uow.prjs.get(prj.prj_id)
        uow.commit()

    return updated_prj


@router.put(
    "/{prj_id}/status/draft",
    summary="Mark Project as Draft",
    description="Updates the lifecycle status of the Project to DRAFT.",
)
def prjs_put_status_draft(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    prj_id: str,
    oda: UnitOfWork,
) -> Status:
    LOGGER.debug("PUT PRJS prjs_put_status_draft prj_id: %s", prj_id)
    # Validate project has scheduling blocks before changing status
    with oda as uow:
        prj = uow.prjs.get(prj_id)
        _validate_project_has_scheduling_blocks(prj)

    with oda as uow:
        uow.status.mark_project_draft(project_id=prj_id, updated_by=auth.user_id)
        uow.commit()
    with oda as uow:
        return uow.status.get_current_status(prj_id)


@router.put(
    "/{prj_id}/status/ready",
    summary="Mark Project as Ready",
    description="Updates the lifecycle status of the Project to READY.",
)
def prjs_put_status_ready(
    auth: Annotated[
        AuthContext,
        Permissions(roles=API_ROLES, scopes={Scope.ODT_READWRITE}),
    ],
    prj_id: str,
    oda: UnitOfWork,
) -> Status:
    LOGGER.debug("prjs_put_status_ready identifier: %s", prj_id)
    with oda as uow:
        prj = uow.prjs.get(prj_id)
        _validate_project_has_scheduling_blocks(prj)

    with oda as uow:
        uow.status.mark_project_ready(project_id=prj_id, updated_by=auth.user_id)
        uow.commit()
    with oda as uow:
        return uow.status.get_current_status(prj_id)
