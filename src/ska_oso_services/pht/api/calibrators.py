import logging
from datetime import timedelta

from fastapi import APIRouter
from ska_aaa_authhelpers.roles import Role
from ska_oso_pdm import Target, TelescopeType

from ska_oso_services.common.auth import Permissions, Scope
from ska_oso_services.common.calibrator_strategy import (
    CalibratorChoice,
    lookup_observatory_calibration_strategy,
)
from ska_oso_services.common.calibrators import (
    ClosestCalibrator,
    HighestCalibrator,
    find_appropriate_calibrators,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["PPT API - Proposal Preparation"])


@router.get(
    "/calibrators",
    summary="Return a list of calibrators for a Target given a strategy",
    dependencies=[Permissions(roles={Role.ANY}, scopes=Scope)],
)
def get_calibrators(
    target: Target,
    telescope: TelescopeType,
    scan_duration_ms: float,
    strategy: CalibratorChoice = CalibratorChoice.HIGHEST_ELEVATION,
) -> list[ClosestCalibrator | HighestCalibrator]:
    """
    returns a list of Calibrator objects from a
    """
    LOGGER.debug("GET /calibrators")

    strategy_object = lookup_observatory_calibration_strategy(strategy.value)

    calibrators = find_appropriate_calibrators(
        target=target,
        strategy=strategy_object,
        scan_duration=timedelta(milliseconds=scan_duration_ms),
        telescope=telescope,
    )

    return calibrators
