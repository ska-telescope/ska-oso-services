import logging

from fastapi import APIRouter
from ska_aaa_authhelpers import Role

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.itfmapper import SubarrayDetail, get_itf_subarrays
from ska_oso_services.common.osdmapper import (
    LOW_ITF_ARRAY_ASSEMBLY,
    Configuration,
    LowSubarray,
    configuration_from_osd,
)
from ska_oso_services.validation.model import ValidationIssue, ValidationIssueType

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/configuration",
    summary="Get static configuration data used by the ODT UI that is sourced from the OSD "
    "and the SKA Low ITF telescope model data.",
    dependencies=[Permissions(roles={Role.ANY}, scopes=Scope)],
)
def configuration_get() -> Configuration:
    LOGGER.debug("GET /configuration")
    configuration = configuration_from_osd()
    # The OSD configuration is cached, whereas the ITF subarray details can be
    # reloaded, so they are attached to the Low_ITF subarray on each request.
    subarrays, issues = _with_itf_subarray_details(configuration, get_itf_subarrays())
    if issues:
        # The ITF data may have been corrected since it was loaded, so check
        # again (at most once per retry interval) before reporting the issues
        subarrays, issues = _with_itf_subarray_details(
            configuration, get_itf_subarrays(refresh=True)
        )

    return configuration.model_copy(
        update={
            "ska_low": configuration.ska_low.model_copy(update={"subarrays": subarrays}),
            "issues": configuration.issues + issues,
        }
    )


def _with_itf_subarray_details(
    configuration: Configuration, subarray_details: list[SubarrayDetail]
) -> tuple[list[LowSubarray], list[ValidationIssue]]:
    subarrays = []
    issues = []
    for index, subarray in enumerate(configuration.ska_low.subarrays):
        if subarray.name != LOW_ITF_ARRAY_ASSEMBLY:
            subarrays.append(subarray)
            continue
        low_itf = subarray.model_copy(update={"subarray_details": subarray_details or None})
        # Checked against the OSD receptors, before any ITF stations are added to them
        issues.extend(_stations_not_in_receptors(low_itf, f"$.ska_low.subarrays[{index}]"))
        subarrays.append(_with_itf_stations_in_receptors(low_itf))
    return subarrays, issues


def _with_itf_stations_in_receptors(subarray: LowSubarray) -> LowSubarray:
    """
    Adds any ITF station ids that are missing from the OSD receptors, so that a
    mismatch between the two sources does not prevent the stations being used.
    """
    receptors = list(subarray.receptors)
    for detail in subarray.subarray_details or []:
        receptors.extend(
            station.id for station in detail.allowed_stations if station.id not in receptors
        )
    return subarray.model_copy(update={"receptors": receptors})


def _stations_not_in_receptors(subarray: LowSubarray, path: str) -> list[ValidationIssue]:
    receptors = set(subarray.receptors)
    issues = []
    for index, detail in enumerate(subarray.subarray_details or []):
        unknown_ids = [
            station.id for station in detail.allowed_stations if station.id not in receptors
        ]
        if unknown_ids:
            issues.append(_station_issue(subarray, detail, unknown_ids, path, index))
    return issues


def _station_issue(
    subarray: LowSubarray,
    detail: SubarrayDetail,
    unknown_ids: list[int],
    path: str,
    index: int,
) -> ValidationIssue:
    return ValidationIssue(
        message=f"The allowed stations {unknown_ids} of the '{detail.name}' subarray are "
        f"not in the OSD receptors of the '{subarray.name}' subarray. They have been added "
        "to its receptors, but may fail validation against it.",
        field=f"{path}.subarray_details[{index}].allowed_stations",
        level=ValidationIssueType.WARNING,
    )
